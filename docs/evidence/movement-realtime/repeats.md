| Série | Buffer | Profil | Max wall / CPU ms | XRUN | Dépassements wall / CPU | Test port MIDI |
|---|---:|---|---:|---:|---:|---|
| live-recorder-overflow | 256 | LIVE_LIGHT | 1.584 / 1.583 | 12 | 0/0 | PASS |
| live-recorder-overflow | 256 | LIVE_NORMAL | 2.283 / 2.282 | 2 | 0/0 | PASS |
| live-recorder-overflow | 256 | STRESS | 9.537 / 9.537 | 4 | 2/2 | FAIL |
| live-recorder-overflow | 512 | LIVE_LIGHT | 9.983 / 2.994 | 6 | 0/0 | PASS |
| live-recorder-overflow | 512 | LIVE_NORMAL | 23.083 / 23.082 | 7 | 1/1 | PASS |
| live-recorder-overflow | 512 | STRESS | 5.927 / 5.926 | 0 | 0/0 | FAIL |
| live-cyclic | 256 | LIVE_LIGHT | 1.267 / 1.266 | 2 | 0/0 | PASS |
| live-cyclic | 256 | LIVE_NORMAL | 6.480 / 6.479 | 12 | 1/1 | PASS |
| live-cyclic | 256 | STRESS | 72.361 / 35.809 | 29 | 4/4 | PASS |
| live-cyclic | 512 | LIVE_LIGHT | 29.807 / 29.806 | 26 | 2/2 | PASS |
| live-cyclic | 512 | LIVE_NORMAL | 2.491 / 1.211 | 2 | 0/0 | PASS |
| live-cyclic | 512 | STRESS | 7.073 / 7.073 | 25 | 0/0 | FAIL |
| live-acyclic-v2 | 256 | LIVE_LIGHT | 18.665 / 18.637 | 22 | 1/1 | PASS |
| live-acyclic-v2 | 256 | LIVE_NORMAL | 111.914 / 21.855 | 20 | 1/1 | PASS |
| live-acyclic-v2 | 256 | STRESS | 101.477 / 33.870 | 40 | 6/4 | PASS |
| live-acyclic-v2 | 512 | LIVE_LIGHT | 6.948 / 6.922 | 25 | 0/0 | PASS |
| live-acyclic-v2 | 512 | LIVE_NORMAL | 1.549 / 1.548 | 0 | 0/0 | PASS |
| live-acyclic-v2 | 512 | STRESS | 80.741 / 80.597 | 17 | 1/1 | FAIL |
| live | 256 | LIVE_LIGHT | 7.068 / 7.067 | 89 | 1/1 | PASS |
| live | 256 | LIVE_NORMAL | 4.554 / 4.542 | 12 | 0/0 | PASS |
| live | 256 | STRESS | 14.327 / 14.171 | 28 | 2/3 | PASS |
| live | 512 | LIVE_LIGHT | 2.691 / 2.690 | 7 | 0/0 | PASS |
| live | 512 | LIVE_NORMAL | 1.523 / 1.522 | 5 | 0/0 | PASS |
| live | 512 | STRESS | 1.983 / 1.983 | 0 | 0/0 | PASS |
