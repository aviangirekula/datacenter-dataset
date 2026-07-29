"""Multi-hazard exposure for data-center facilities.

Samples natural-hazard layers at each facility's building-level coordinate to
produce a facility x hazard exposure table. Hazard layers come from the same
public sources used by Bor, Oughton & Weigel (MHTran, Zenodo 10.5281/zenodo.20331026)
so this analysis stays methodologically consistent with the lab's transmission
work, but applied to data-center locations instead of substations.

IMPORTANT - honesty: each hazard column records the raw hazard value sampled at
the point (e.g. seismic PGA in g, lightning flash rate). Turning exposure into
damage/loss needs vulnerability curves, which are a later step and should be
aligned with Dennies Bor. Coverage (how many facilities got a non-null value) is
reported per hazard and never silently filled.
"""
