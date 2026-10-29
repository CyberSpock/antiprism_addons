# inscribe

[Program index](README.md) · [Python source](../../inscribe.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: inscribe.py [-h] -a vN|eN|fN -b vN|eN|fN [-v] [--keep-temp] [--version]
                   model1 model2

Scale one OFF model to match a selected element radius of another. Model 2 is
uniformly scaled so that the distance of its selected vertex, edge midpoint,
or face centroid from its model centroid matches that of model 1's selected
element. The two models are combined as OFF on stdout; neither source is
modified.

positional arguments:
  model1                first OFF file or Antiprism built-in model
  model2                second OFF file or Antiprism built-in model

options:
  -h, --help            show this help message and exit
  -a, --first-element vN|eN|fN
                        element in model 1 setting target radius
  -b, --second-element vN|eN|fN
                        element in model 2 to match to model 1
  -v, --verbose         print selected radii, scale factor, and commands to
                        stderr
  --keep-temp           preserve temporary files and report their directory
  --version             show program's version number and exit
```
