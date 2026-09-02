"""
Esqueleto del backtest WALK-FORWARD (versión pública, sanitizada)
==================================================================
Este archivo muestra el ANDAMIAJE del backtest que garantiza ausencia de
look-ahead y salidas conservadoras. La lógica de DETECCIÓN real (zigzag,
validación de ondas, línea 1-B, screener de ruptura) NO se incluye: se
representa aquí como una interfaz `detectar_senal(df_visible)` que devuelve
una señal o None.

Por qué esto importa (es el corazón de la auditoría):
  1. Para cada vela t, la detección solo ve `df.iloc[:t+1]`  → sin futuro.
  2. La entrada es el CIERRE de la vela de ruptura; el seguimiento empieza
     en t+1 (la vela de entrada no se re-evalúa).
  3. En cada vela de salida se comprueba el STOP (Low) ANTES que el TARGET
     (High): si ambos caen en la misma vela semanal, se asume el peor caso.

Estas tres decisiones son las que hicieron caer el Profit Factor de 3,87 a
2,74 al eliminar el look-ahead. Ver docs/writeup-completo.md y
docs/auditoria-codigo.md.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd


# --- Interfaz de detección (implementación real NO pública) -----------------
@dataclass
class Senal:
    fecha_ruptura: pd.Timestamp
    precio_entrada: float      # cierre de la vela de ruptura
    stop: float                # p.ej. punto 0 (Escenario A)
    target_1: float
    target_2: float


def detectar_senal(df_visible: pd.DataFrame) -> Optional[Senal]:
    """
    STUB público. En el sistema real, aquí vive el pipeline de detección
    (zigzag ATR → Onda 1 → ABC Onda 2 → línea 1-B → ruptura confirmada),
    que se ejecuta SOLO sobre `df_visible` (datos hasta la vela actual).
    Devuelve una Senal si la última vela de `df_visible` confirma una
    ruptura válida, o None.
    """
    raise NotImplementedError(
        "Módulo de detección no público — ver README, sección 'Qué se publica y qué no'."
    )


# --- Fase 1: reconstrucción walk-forward (sin look-ahead) -------------------
def generar_senales_walkforward(
    df: pd.DataFrame,
    min_bars: int = 104,
    dedup_weeks: int = 12,
) -> list[Senal]:
    """
    Para cada vela t (desde min_bars), rehace la detección usando ÚNICAMENTE
    df.iloc[:t+1]. Ninguna función accede a datos posteriores a t.
    Deduplicación temporal: no se emiten dos señales del mismo ticker en
    menos de `dedup_weeks` semanas.
    """
    senales: list[Senal] = []
    n = len(df)
    ultima_t = -dedup_weeks - 1

    for t in range(min_bars, n):
        if t - ultima_t < dedup_weeks:
            continue

        df_visible = df.iloc[: t + 1]        # <-- la clave: solo pasado y presente
        senal = detectar_senal(df_visible)
        if senal is not None:
            senales.append(senal)
            ultima_t = t

    return senales


# --- Fase 2: seguimiento de la operación (salidas conservadoras) ------------
@dataclass
class Resultado:
    exit_reason: str
    return_pct: float
    holding_weeks: int
    max_drawdown_pct: float


def seguir_trade(
    df: pd.DataFrame,
    entry_iloc: int,
    entry_price: float,
    stop: float,
    target_1: float,
    target_2: float,
    max_holding: int = 52,
) -> Resultado:
    """
    Rastrea la operación semana a semana desde entry_iloc + 1.
    Prioridad de cierre (conservadora):
      1) STOP (Low <= stop)  -> se comprueba PRIMERO
      2) TARGET_2 (High >= target_2)
      3) TARGET_1 (se registra, no cierra; sigue para T2 o timeout)
    Si en una misma vela se tocan stop y target, GANA el stop (peor caso).
    """
    last = len(df) - 1
    max_dd = 0.0
    hit_t1 = False
    exit_price, exit_reason, holding = entry_price, "TIMEOUT", 0

    for week in range(1, max_holding + 1):
        i = entry_iloc + week
        if i > last:
            exit_reason = "END_DATA"
            exit_price = float(df["Close"].iloc[last])
            holding = last - entry_iloc
            break

        low = float(df["Low"].iloc[i])
        high = float(df["High"].iloc[i])
        holding = week

        dd = (low - entry_price) / entry_price
        max_dd = min(max_dd, dd)

        # 1) STOP primero (conservador)
        if low <= stop:
            exit_price, exit_reason = stop, "STOP"
            break
        # 2) TARGET_2
        if high >= target_2:
            exit_price, exit_reason = target_2, "TARGET_2"
            hit_t1 = True
            break
        # 3) TARGET_1 (solo se registra)
        if not hit_t1 and high >= target_1:
            hit_t1 = True
    else:
        final = min(entry_iloc + max_holding, last)
        exit_price = float(df["Close"].iloc[final])
        holding = final - entry_iloc
        exit_reason = "TIMEOUT"

    if exit_reason in ("TIMEOUT", "END_DATA") and hit_t1:
        exit_reason = "TIMEOUT_T1"

    return Resultado(
        exit_reason=exit_reason,
        return_pct=(exit_price - entry_price) / entry_price,
        holding_weeks=holding,
        max_drawdown_pct=max_dd,
    )
