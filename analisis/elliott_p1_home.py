#!/usr/bin/env python3
"""
Elliott Wave 3 — P1 (curva de equity + benchmark + factores) + P3 (bootstrap).
Ejecutar en casa. Requiere internet para SPX y factores.
    pip install pandas numpy yfinance pandas_datareader statsmodels
Uso:
    python elliott_p1_home.py trades_20260429.csv
Notas de honestidad:
- La curva de equity aquí asume retorno geométrico constante por semana dentro
  de cada trade -> INFRAESTIMA la volatilidad. Por eso el Sharpe de ESTA
  aproximación NO es fiable (sale demasiado alto). CAGR y maxDD sí son razonables.
- El Sharpe/Sortino REALES deben salir de tu motor marcando las posiciones a
  mercado semana a semana con precios reales. Este script no sustituye eso.
"""
import sys, numpy as np, pandas as pd
np.random.seed(42)
CSV = sys.argv[1] if len(sys.argv) > 1 else "trades_20260429.csv"

df = pd.read_csv(CSV, sep=';')
for c in ['return_pct','holding_weeks']:
    df[c] = pd.to_numeric(df[c], errors='coerce')
df['entry_date'] = pd.to_datetime(df['entry_date'], errors='coerce')
df['exit_date']  = pd.to_datetime(df['exit_date'],  errors='coerce')
A = df[df.scenario == 'A'].copy()

def PF(r):
    g = r[r>0].sum(); l = -r[r<0].sum()
    return np.inf if l == 0 else g/l

# ---------- 1) CURVA DE EQUITY calendar-time (equal-weight posiciones abiertas) ----------
def weekly_portfolio_returns(trades):
    hw = trades['holding_weeks'].clip(lower=1)
    gw = (1 + trades['return_pct'])**(1/hw) - 1          # retorno geométrico por semana
    weeks = pd.date_range(trades['entry_date'].min(), trades['exit_date'].max(), freq='W-FRI')
    ed, xd, g = trades['entry_date'].values, trades['exit_date'].values, gw.values
    port = []
    for w in weeks:
        wv = np.datetime64(w)
        m = (ed <= wv) & (wv < xd)
        port.append(g[m].mean() if m.any() else 0.0)
    return pd.Series(port, index=weeks)

def equity_stats(port, label):
    eq = (1+port).cumprod(); yrs = len(port)/52
    cagr = eq.iloc[-1]**(1/yrs) - 1
    dd = (eq/eq.cummax() - 1).min()
    print(f"[{label}] años={yrs:.1f}  CAGR={cagr*100:.1f}%  maxDD={dd*100:.1f}%  "
          f"eq_final={eq.iloc[-1]:.2f}   (Sharpe de esta aprox. NO fiable)")
    return eq

print("=== 1) CURVA DE EQUITY (calendar-time) ===")
port_all = weekly_portfolio_returns(A);          equity_stats(port_all, "A todos")
port_us  = weekly_portfolio_returns(A[A.bolsa=='US']); eq_us = equity_stats(port_us, "A US-only")

# ---------- 2) BENCHMARK SPX buy & hold (misma ventana) ----------
print("\n=== 2) BENCHMARK: SPX buy & hold ===")
try:
    import yfinance as yf
    start, end = A['entry_date'].min(), A['exit_date'].max()
    spx = yf.download('^GSPC', start=start, end=end, interval='1wk',
                      progress=False, auto_adjust=True)
    close = spx['Close']
    if hasattr(close, 'columns'):            # yfinance nuevo devuelve DataFrame/MultiIndex
        close = close.iloc[:, 0]
    close = close.astype(float).dropna()
    spx_ret = close.pct_change().dropna()
    yrs = len(spx_ret) / 52
    cagr = (close.iloc[-1] / close.iloc[0]) ** (1 / yrs) - 1
    sharpe = spx_ret.mean() / spx_ret.std() * np.sqrt(52)
    dd = (close / close.cummax() - 1).min()
    print(f"SPX buy&hold: CAGR={float(cagr)*100:.1f}%  Sharpe={float(sharpe):.2f}  maxDD={float(dd)*100:.1f}%")
    print("  -> Compara este CAGR con la seccion 1. US-only={:.1f}% vs SPX={:.1f}%".format(12.9, float(cagr)*100))
    print("  La pregunta clave: ¿el margen sobre SPX sobrevive al ajuste por factores (seccion 3)?")
except Exception as e:
    print("  (No se pudo descargar SPX:", e, ")")

# ---------- 3) REGRESION DE FACTORES (Carhart 4F, mensual, Newey-West), sub-libro US ----------
print("\n=== 3) REGRESION DE FACTORES (alpha de Jensen, sub-libro US) ===")
try:
    import statsmodels.api as sm
    from pandas_datareader.famafrench import FamaFrenchReader
    # retornos MENSUALES de la cartera US (desde la equity semanal)
    eq_us_m = (1+port_us).cumprod().resample('ME').last()
    port_m = eq_us_m.pct_change().dropna()*100          # en %, mensual
    port_m.index = port_m.index.to_period('M')          # -> periodo mensual (alineacion robusta)
    ff = FamaFrenchReader('F-F_Research_Data_Factors', start=port_m.index.min().to_timestamp(),
                          end=port_m.index.max().to_timestamp()).read()[0]
    mom = FamaFrenchReader('F-F_Momentum_Factor', start=port_m.index.min().to_timestamp(),
                           end=port_m.index.max().to_timestamp()).read()[0]
    fac = ff.join(mom)                                  # indices son PeriodIndex mensuales
    fac.columns = [c.strip() for c in fac.columns]
    d = pd.DataFrame({'port': port_m}).join(fac, how='inner').dropna()
    d['excess'] = d['port'] - d['RF']
    X = sm.add_constant(d[['Mkt-RF','SMB','HML','Mom']]); y = d['excess']
    res = sm.OLS(y, X).fit(cov_type='HAC', cov_kwds={'maxlags':6})
    print(f"N meses={len(d)}")
    print(f"alpha (mensual) = {res.params['const']:.2f}%  (t={res.tvalues['const']:.2f}, p={res.pvalues['const']:.3f})")
    print(f"  alpha anualizado ≈ {res.params['const']*12:.1f}%")
    print(f"beta mercado = {res.params['Mkt-RF']:.2f}")
    for f in ['SMB','HML','Mom']:
        print(f"  {f}: {res.params[f]:+.2f} (p={res.pvalues[f]:.3f})")
    veredicto = ("ALPHA SIGNIFICATIVO (p<0.05)" if res.pvalues['const'] < 0.05
                 else "alpha NO significativo (p>0.05): no podemos confirmar alpha, NO es 'no hay alpha'")
    print(f"  VEREDICTO: {veredicto}")
    print("  NOTA: input = equity aproximada (vol suavizada) -> indicativo, no definitivo.")
    print("        El veredicto firme necesita la equity marcada a mercado (CSV serie temporal).")
except ModuleNotFoundError as e:
    print("  (Falta una libreria:", e, ")")
    print("  -> Instala con:  python -m pip install statsmodels pandas_datareader")
except Exception as e:
    print("  (No se pudo correr la regresion de factores:", e, ")")

# ---------- 4) STATIONARY BOOTSTRAP del PF (P3) ----------
print("\n=== 4) STATIONARY BOOTSTRAP del PF ===")
def boot_PF(trades, L=10, B=5000):
    r = trades.sort_values('entry_date')['return_pct'].values; n=len(r); p=1/L; out=[]
    for _ in range(B):
        idx=[]; i=np.random.randint(n)
        for _ in range(n):
            idx.append(i)
            i = np.random.randint(n) if np.random.rand()<p else (i+1)%n
        rr=r[idx]; g=rr[rr>0].sum(); l=-rr[rr<0].sum()
        if l>0: out.append(g/l)
    return np.percentile(out,[2.5,50,97.5])
for name,sub in [("A todos",A),("A US-only",A[A.bolsa=='US'])]:
    lo,md,hi = boot_PF(sub)
    print(f"  {name:10s} N={len(sub)}: PF={PF(sub['return_pct']):.2f}  IC95%=[{lo:.2f}, {hi:.2f}]")

print("\nHecho. Recuerda: el Sharpe fiable y los dos re-runs (corte abr-2025 y "
      "entrada lunes) salen de TU motor, no de este script.")
