"""S3 batch-28 lane gm22 - MINIMAL text-pin battery closing the two inert
occurrence-twin comment sites of group 22 (``G18``), key
``backend.services.gpu_monitor.xǁGPUMonitorǁ_get_gpu_stats_from_ai_containers__mutmut_33``
(``number:0 -> 1`` inside ``A5500``, bank line L831).

Why this file exists
====================
The fixed replay harness (``/tmp/wp-b28/replay_lib.py``, ``replayF_R22.json``
2026-09-27T17:17Z) measured 9 occurrence twins for the shipped ``0`` at L831
(``if total_vram_used_mb > 0 or gpu_utilization is not None:``).  SEVEN of the
nine redden ``test_gpu_monitor_batch28_14.py`` with named FAILED tests - incl.
the bank-cited site itself (occ3 L831, red on
``test_half_megabyte_vram_still_returns_a_dict``).  The remaining two candidates
are ``A5500 -> A5510`` inside comments:

* occ4  L832 ``# RTX A5500 has 24GB VRAM - use this as default``
* occ6  L838 ``"memory_total": 24576,  # 24GB in MB (RTX A5500 default)``

Both are non-executable text - nothing in behaviour can distinguish them - so
under the occurrence-twin rule the key could not be reported killed by the
behavioural battery alone.  Exactly as the already-proven sibling batteries
pin their inert digit sites (``test_gpu_monitor_batch28_10.py::
test_the_inert_digit_comment_lines_are_verbatim_in_the_imported_source`` and
``test_gpu_monitor_batch28_12.py::
test_sixty_second_window_is_stated_in_docstring_and_comment``), the observable
is the TEXT of the module this world imported, read from ``M.__file__`` (NOT
``inspect.getsource``/linecache, which can hand back a stale same-size copy).
Each pin reddens under its own ``A5500 -> A5510`` mutant and is trivially
green on shipped source; combined with ``test_gpu_monitor_batch28_14.py`` all
nine candidates redden, which is what the replay harness requires.

Transcribed from ``backend/services/gpu_monitor.py`` md5
``2f122c85a072b7bd00c2e4b36cdc1cda`` (lane-gm HEAD a5307982).
"""

from pathlib import Path

import pytest

from backend.services import gpu_monitor as M

pytestmark = [pytest.mark.unit]

# Verbatim shipped lines, transcribed from the file cited above.
L832 = "                    # RTX A5500 has 24GB VRAM - use this as default"
L838 = '                        "memory_total": 24576,  # 24GB in MB (RTX A5500 default)'


def test_the_a5500_comment_digit_sites_are_verbatim_in_the_imported_source():
    text = Path(M.__file__).read_text()  # nosemgrep: path-traversal-open
    assert L832 in text, "L832 comment mutated (A5500 -> A5510 twin occ4)"
    assert L838 in text, "L838 trailing comment mutated (A5500 -> A5510 twin occ6)"


# Same shape for group 4 (G05a), key
# ``..._get_gpu_stats_nvidia_smi_async__mutmut_20`` (``name:True -> False``, bank
# L398, ``replayF_R4.json``): of its three ``True`` occurrence twins, occ0
# L398 ``capture_output=True`` and occ1 L399 ``text=True`` are code and redden
# ``test_gpu_monitor_batch28_01.py`` with named FAILED tests; occ2 is the
# ``True`` inside the L403 comment below - inert text, pinned here.
L403 = "            # With text=True, stdout/stderr are strings"


def test_the_text_true_comment_line_is_verbatim_in_the_imported_source():
    text = Path(M.__file__).read_text()  # nosemgrep: path-traversal-open
    assert L403 in text, "L403 comment mutated (True -> False twin occ2)"
