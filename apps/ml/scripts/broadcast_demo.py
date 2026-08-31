"""Render broadcast-style strategy panels from a real 2026 race.

Reproduces the two F1 Insights graphics — Pit Window and Pit Strategy Battle —
on actual race data, so the output format can be judged before the simulator
and the genetic algorithm exist.

    uv run python scripts/broadcast_demo.py --round 11 --lap 20
"""

from __future__ import annotations

import argparse
import sys
import warnings

import pandas as pd

from boxbox_ml import cache, features, ingest, insights

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

# The Windows console defaults to cp1252, which cannot encode the box-drawing
# characters or the accented Spanish labels below.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BOX = "═" * 66


def panel(title: str, rows: list[str]) -> None:
    """Print a titled panel in the register of a broadcast overlay."""
    print(f"\n╔{BOX}╗")
    print(f"║ {title:<64} ║")
    print(f"╠{BOX}╣")
    for row in rows:
        print(f"║ {row:<64} ║")
    print(f"╚{BOX}╝")


def build_driver(row: pd.Series) -> insights.Driver:
    """Map a lap record onto the insight model's driver state."""
    return insights.Driver(
        code=row["Driver"],
        compound=str(row["Compound"]),
        tyre_age=int(row["TyreLife"]) if pd.notna(row["TyreLife"]) else 0,
        degradation_s=float(row["degradation_s"]) if pd.notna(row["degradation_s"]) else 0.0,
        degradation_rate=(
            float(row["degradation_rate_s_per_lap"])
            if pd.notna(row["degradation_rate_s_per_lap"])
            else 0.0
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--round", type=int, default=11)
    parser.add_argument("--lap", type=int, default=20)
    args = parser.parse_args()

    print(f"cache: {cache.enable()}")
    frame = features.build(ingest.load_race(args.season, args.round))
    frame["LapNumber"] = frame["LapNumber"].astype(int)

    circuit = frame["circuit"].iloc[0]
    total = int(frame["total_laps"].iloc[0])
    lap = frame[frame["LapNumber"] == args.lap].sort_values("Position")
    if lap.empty:
        raise SystemExit(f"no data for lap {args.lap}")

    print(f"\n{args.season} · {circuit} · vuelta {args.lap} de {total}")

    # ------------------------------------------------------------ pit window
    rows = []
    for _, row in lap.head(8).iterrows():
        if pd.isna(row["Position"]):
            continue
        driver = build_driver(row)
        window = insights.pit_window(
            driver,
            laps_remaining=total - args.lap,
            expected_stint_life=22,
        )
        if window is None:
            ventana = "sin proyectar *"
        else:
            opens, closes = window
            ventana = f"vueltas {args.lap + opens}-{args.lap + closes}"
        rows.append(
            f"P{int(row['Position']):<2} {driver.code:<4} {driver.compound[:3]:<3} "
            f"{driver.tyre_age:>2}v   {ventana:<22} deg {driver.degradation_s:+.2f} s"
        )
    rows.append("")
    rows.append("* goma plana o mejorando: no hay cruce proyectable todavia")
    panel("VENTANA DE BOXES", rows)

    # -------------------------------------------------- pit strategy battle
    ordered = lap.dropna(subset=["Position"]).sort_values("Position")
    battles = []
    for i in range(len(ordered) - 1):
        leader_row, chaser_row = ordered.iloc[i], ordered.iloc[i + 1]
        gap = chaser_row.get("gap_ahead_s")
        if pd.isna(gap) or not (0 < gap < 6):
            continue
        leader, chaser = build_driver(leader_row), build_driver(chaser_row)
        # Undercutting a car that has just stopped is meaningless: it will not
        # respond, and its fresh tyres are not degrading yet.
        if leader.tyre_age <= 2 or chaser.tyre_age <= 2:
            continue
        result = insights.strategy_battle(chaser, leader, float(gap))
        battles.append((chaser, leader, gap, result))

    if not battles:
        panel("DUELO DE ESTRATEGIA", ["Sin duelos dentro de 6 s en esta vuelta."])
    else:
        battles.sort(key=lambda b: -b[3].probability)
        for chaser, leader, gap, result in battles[:4]:
            panel(
                f"DUELO DE ESTRATEGIA — {chaser.code} vs {leader.code}",
                [
                    f"Diferencia actual         {gap:.2f} s",
                    f"{chaser.code} en {chaser.compound[:3]} de {chaser.tyre_age} vueltas"
                    f"   (pierde {chaser.degradation_s:+.2f} s/vuelta)",
                    f"{leader.code} en {leader.compound[:3]} de {leader.tyre_age} vueltas"
                    f"   (se degrada {leader.degradation_rate:+.3f} s/vuelta)",
                    "",
                    f"Si {chaser.code} para ahora y {leader.code} responde en "
                    f"{result.best_response_lap} vueltas:",
                    f"   gana {result.per_lap_gain:.2f} s por vuelta",
                    f"   diferencia proyectada  {result.gap_after:+.2f} s",
                    "",
                    f"   >> {result.headline()}",
                ],
            )

    print(
        "\nNota: el modelo no incluye tráfico en la vuelta de salida, respuesta\n"
        "inmediata del rival ni neutralizaciones. Bajo Safety Car la cuenta\n"
        "cambia por completo: parar cuesta ~0 posiciones en lugar de 2."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
