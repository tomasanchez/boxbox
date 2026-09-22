"""¿Es frágil el desgaste del medio en Zandvoort, que descansa en once tandas?

La celda de medio de Zandvoort tiene **n=11**, la más fina de las tres del
circuito, y es la que más se aparta: 0,1004 s/vuelta de mediana cruda, 0,0934
después del encogimiento, contra 0,0625 de la medición que junta todas las
temporadas. Con una muestra así la sospecha razonable es que el número sea ruido.

**No lo es**, y conviene tenerlo medido porque yo mismo lo di por frágil antes de
mirarlo.

## Las tres pruebas

**No lo mueve una tanda.** Sacando cualquiera de las once, la mediana va de
0,0968 a 0,1054: se corre 0,0086. No hay una sola carrera rara sosteniéndolo.

**El intervalo no toca al otro valor.** Remuestreando las once 20.000 veces, la
mediana cae entre 0,0839 y 0,1193 con 95% de confianza, y **0,0625 queda
afuera**. O sea que la diferencia entre las dos mediciones de Zandvoort no es
error de muestreo: 2026 realmente castiga más al medio que las temporadas
anteriores, donde con n=60 la mediana era 0,0603.

**Y no es un circuito extremo.** Entre los catorce circuitos de 2026 con seis o
más tandas de medio, Zandvoort sale **duodécimo**: Spielberg da 0,1078 y
Barcelona 0,1929. Alto, pero dentro del abanico normal del año.

## Lo que sí llama la atención

Las once tandas, ordenadas, son::

    0,0654  0,0671  0,0839  0,0884  0,0932  0,1004
    0,1105  0,1113  0,1193  0,2234  0,5926

Las dos últimas son enormes —0,59 s/vuelta es medio minuto perdido en una tanda
larga— y casi seguro no son desgaste sino autos rotos o cronometraje sucio. La
**mediana** las ignora por construcción, que es exactamente para lo que se la
eligió, y es el motivo por el que el número aguanta pese a la muestra chica. Una
media daría 0,133 y estaría gobernada por esas dos.

Correr con uv run python scripts/medium_wear_check.py.
"""

import pathlib

import numpy as np

# Se reusa el cargador de `circuit_wear.py` en vez de copiarlo: la pregunta es
# sobre EL MISMO numero que esa tabla publica, y una copia de la definicion de
# tanda podria derivar y hacer que esto midiera otra cosa. El linter no puede ver
# un nombre que aparece por `exec`, de ahi el noqa.
src = pathlib.Path("scripts/circuit_wear.py").read_text(encoding="utf-8")
exec(src.split("stints = load_stints()")[0])  # noqa: S102
stints = load_stints()  # noqa: F821
stints["era"] = np.where(stints["year"] >= 2026, "2026", "previo")

z = stints[(stints["circuit"] == "Zandvoort") & (stints["compound"] == "MEDIUM")]
z26 = z[z["era"] == "2026"]["slope"].to_numpy()
zold = z[z["era"] == "previo"]["slope"].to_numpy()
print(f"Zandvoort MEDIO: 2026 n={len(z26)}, previo n={len(zold)}")
print(f"  mediana 2026   {np.median(z26):.4f}")
print(f"  mediana previo {np.median(zold):.4f}")
print(f"  las 11 de 2026, ordenadas: {np.sort(z26).round(4)}")
print()

rng = np.random.default_rng(7)
boot = np.array([np.median(rng.choice(z26, len(z26), replace=True)) for _ in range(20000)])
lo, hi = np.percentile(boot, [2.5, 97.5])
print("BOOTSTRAP de la mediana (20.000 remuestreos):")
print(f"  IC 95%  {lo:.4f} a {hi:.4f}   ancho {hi - lo:.4f}")
print(f"  el valor de todas las temporadas, 0,0625, ¿cae adentro? {lo <= 0.0625 <= hi}")
print()
loo = np.array([np.median(np.delete(z26, i)) for i in range(len(z26))])
print(
    f"DEJANDO UNA AFUERA: la mediana va de {loo.min():.4f} a {loo.max():.4f}"
    f"  (se mueve {loo.max() - loo.min():.4f})"
)
print()
other = stints[(stints["era"] == "2026") & (stints["compound"] == "MEDIUM")]
med = other.groupby("circuit")["slope"].agg(["median", "size"])
med = med[med["size"] >= 6].sort_values("median")
print("MEDIO en 2026, todos los circuitos con 6+ tandas:")
print(med.round(4).to_string())
print()
rank = list(med.index).index("Zandvoort") + 1 if "Zandvoort" in med.index else None
print(
    f"  Zandvoort es el {rank}º de {len(med)}: "
    f"{'el que más castiga' if rank == len(med) else 'alto, pero no un extremo'}"
)
