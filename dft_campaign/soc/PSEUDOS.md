# SOC pseudopotential manifest (listed separately per the manifest rule)

Fully relativistic PSL 1.0.0 kjpaw PAW sets from
<https://pseudopotentials.quantum-espresso.org/upf_files/>. They are NOT
bundled in this repository; PSlibrary pseudopotentials retain their own
license (GPL). Downloaded 2026-09-08 and staged to
`/scratch/general/vast/$USER/mpt_soc/pseudos/` for the SOC runs.

sha256 hashes, frozen:

```
5b168106e9d215c487c06a0446d05f665b39bed5af92b83e078f2c03ad3bb1cb  Hf.rel-pbe-spn-kjpaw_psl.1.0.0.UPF
0d4be41e6095e403d92e7d070cc7d5d7eea54f182a55e93af93c4d497e050b76  Mo.rel-pbe-spn-kjpaw_psl.1.0.0.UPF
5d00b9b953e8d44e664881caf4cd37d6a92d2fdab6c4aa1beebe4605932cd5ea  S.rel-pbe-n-kjpaw_psl.1.0.0.UPF
00ce9d578a761fae3624ff83b1bf8609f82619a0d4ec0fe6fa85f0f0463ccfda  Se.rel-pbe-n-kjpaw_psl.1.0.0.UPF
db65da14048bde30bb3e11c2c09fdcbb2cf2e0f2992fae5390e96110dc8c84cc  Te.rel-pbe-n-kjpaw_psl.1.0.0.UPF
51432892fa0c8acaabedaeb3d367d37da9dfb3b5e2381b4b25b2f485490cc0f8  W.rel-pbe-spn-kjpaw_psl.1.0.0.UPF
b7c14966f8e7b07ed678d8f62c1488d03ee35caa1aa172cb3af6952b1efe3ba7  Zr.rel-pbe-spn-kjpaw_psl.1.0.0.UPF
```

Cutoffs used for every SOC run: `ecutwfc = 60 Ry`, `ecutrho = 400 Ry`
(max suggested across the set is 55/373 Ry, for W).

Note: the SOC gap is computed with a *different* pseudopotential family
(PSL PAW) than the scalar-relativistic campaign (GBRV USPP), so the
`soc_shift_ev` field mixes the SOC effect with a small family/cutoff
difference. It is a screening quantity, consistent with the manifest's
validity constraints.
