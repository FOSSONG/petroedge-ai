import lasio

las = lasio.read(
    "data/mywell.las"
)

for curve in las.curves:
    print(curve.mnemonic)