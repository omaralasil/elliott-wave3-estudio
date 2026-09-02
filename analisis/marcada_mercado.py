#!/usr/bin/env python3
"""
Elliott Wave 3 — Curva de equity MARCADA A MERCADO (real) + regresión de factores.

Reconstruye la cartera equal-weight semana a semana revalorizando las posiciones
ABIERTAS a precio de mercado (precios semanales de Yahoo Finance), en vez de la
aproximación que suavizaba el retorno de cada trade. Con esto:
  - el beta vuelve a su nivel real (una cartera long-only US NO puede tener beta 0,11)
  - el Sharpe/maxDD son fiables
  - la regresión alpha vs beta es la DEFINITIVA

Requiere internet.
    python -m pip install pandas numpy yfinance pandas_datareader statsmodels
Uso:
    python elliott_equity_real.py trades_20260817.csv
Salida:
    - imprime CAGR, Sharpe, maxDD reales (A todos y A US)
    - guarda equity_real_all.csv y equity_real_us.csv (fecha;valor)  <-- esto es lo que faltaba
    - corre la regresión de factores sobre la equity US REAL

Nota honesta: los retornos se re-derivan de precios de Yahoo (auto-ajustados), así que
el CAGR puede diferir un poco del de tu motor (ajustes/timing). Pero la DESCOMPOSICIÓN
alpha/beta es fiable porque usa el co-movimiento semanal real con el mercado.
Los tickers deslistados que Yahoo no encuentre se excluyen (se informa cuántos).
"""
import sys, numpy as np, pandas as pd
np.random.seed(42)
CSV = sys.argv[1] if len(sys.argv) > 1 else "trades_20260817.csv"

df = pd.read_csv(CSV, sep=';')
df['entry_date'] = pd.to_datetime(df['entry_date'], errors='coerce')
df['exit_date']  = pd.to_datetime(df['exit_date'],  errors='coerce')
A = df[df.scenario == 'A'].dropna(subset=['entry_date','exit_date']).copy()

def build_equity(trades, label, outfile):
    import yfinance as yf
    tickers = sorted(trades['ticker'].unique().tolist())
    start = trades['entry_date'].min(); end = trades['exit_date'].max() + pd.Timedelta(days=7)
    print(f"\n[{label}] descargando {len(tickers)} tickers de Yahoo (semanal)...")
    px = yf.download(tickers, start=start, end=end, interval='1wk',
                     auto_adjust=True, progress=False)['Close']
    if isinstance(px, pd.Series):            # un solo ticker
        px = px.to_frame(tickers[0])
    px = px.dropna(axis=1, how='all')         # quita tickers sin datos (deslistados)
    faltan = [t for t in tickers if t not in px.columns]
    if faltan:
        print(f"  ⚠ {len(faltan)} tickers sin datos en Yahoo (excluidos): {faltan[:8]}{'...' if len(faltan)>8 else ''}")
    rets = px.pct_change()

    # cartera equal-weight de posiciones ABIERTAS cada semana
    port  = pd.Series(0.0, index=rets.index)
    count = pd.Series(0.0, index=rets.index)
    used = 0
    for _, tr in trades.iterrows():
        tk = tr['ticker']
        if tk not in rets.columns: continue
        mask = (rets.index > tr['entry_date']) & (rets.index <= tr['exit_date'])
        r = rets[tk].where(mask).fillna(0.0)
        port  += r
        count += mask.astype(float)
        used  += 1
    port = (port / count.replace(0, np.nan)).fillna(0.0)   # media; semanas sin posición = 0 (cash)

    eq = (1 + port).cumprod()
    yrs = len(port) / 52
    cagr = eq.iloc[-1] ** (1/yrs) - 1
    sharpe = port.mean() / port.std() * np.sqrt(52) if port.std() > 0 else float('nan')
    dd = (eq / eq.cummax() - 1).min()
    exposure = (count > 0).mean()
    avg_pos = count[count > 0].mean()
    print(f"[{label}] trades usados={used}  años={yrs:.1f}  CAGR={cagr*100:.1f}%  "
          f"Sharpe={sharpe:.2f}  maxDD={dd*100:.1f}%  (invertido {exposure*100:.0f}% del tiempo, "
          f"~{avg_pos:.0f} posiciones abiertas de media)")
    eq.rename('valor_cartera').to_csv(outfile, sep=';', header=True)
    print(f"       -> guardado {outfile}")
    return port

print("=== CURVA DE EQUITY MARCADA A MERCADO (real) ===")
port_all = build_equity(A,                 "A todos",  "equity_real_all.csv")
port_us  = build_equity(A[A.bolsa=='US'],  "A US-only","equity_real_us.csv")

# ---------- REGRESIÓN DE FACTORES sobre la equity US REAL ----------
print("\n=== REGRESIÓN DE FACTORES (Carhart 4F, mensual, Newey-West) sobre equity US REAL ===")
try:
    import statsmodels.api as sm
    from pandas_datareader.famafrench import FamaFrenchReader
    eq_us_m = (1+port_us).cumprod().resample('ME').last()
    port_m = eq_us_m.pct_change().dropna()*100
    port_m.index = port_m.index.to_period('M')
    ff  = FamaFrenchReader('F-F_Research_Data_Factors',  start=port_m.index.min().to_timestamp(),
                           end=port_m.index.max().to_timestamp()).read()[0]
    mom = FamaFrenchReader('F-F_Momentum_Factor',        start=port_m.index.min().to_timestamp(),
                           end=port_m.index.max().to_timestamp()).read()[0]
    fac = ff.join(mom); fac.columns = [c.strip() for c in fac.columns]
    d = pd.DataFrame({'port': port_m}).join(fac, how='inner').dropna()
    d['excess'] = d['port'] - d['RF']
    X = sm.add_constant(d[['Mkt-RF','SMB','HML','Mom']]); y = d['excess']
    res = sm.OLS(y, X).fit(cov_type='HAC', cov_kwds={'maxlags':6})
    print(f"N meses={len(d)}")
    print(f"alpha (mensual) = {res.params['const']:.2f}%  (t={res.tvalues['const']:.2f}, p={res.pvalues['const']:.3f})")
    print(f"  alpha anualizado ≈ {res.params['const']*12:.1f}%")
    print(f"beta mercado = {res.params['Mkt-RF']:.2f}  <-- ahora deberia ser ~0.7-1.1 si esta bien")
    for f in ['SMB','HML','Mom']:
        print(f"  {f}: {res.params[f]:+.2f} (p={res.pvalues[f]:.3f})")
    veredicto = ("ALPHA SIGNIFICATIVO (p<0.05)" if res.pvalues['const'] < 0.05
                 else "alpha NO significativo (p>0.05): no se puede confirmar alpha")
    print(f"  VEREDICTO (definitivo): {veredicto}")
    print(f"  R² = {res.rsquared:.2f} (cuanto explica el mercado+factores de tu retorno)")
except ModuleNotFoundError as e:
    print("  (Falta libreria:", e, ") -> python -m pip install statsmodels pandas_datareader")
except Exception as e:
    print("  (No se pudo correr la regresion:", e, ")")

print("\nHecho. Pega TODA la salida. El beta ya deberia ser realista; el alpha que quede es el de verdad.")
