"""P1 bake-off cases (spec §3.7). Security-camera framing; realistic and
non-graphic (spec §3.8); the identity is invented, never a real person."""

from __future__ import annotations

from dataclasses import dataclass

DAY = (
    "Photorealistic still from a fixed outdoor security camera mounted under the eaves about "
    "three meters high, wide-angle lens looking down at the scene, daytime, natural color, "
    "ordinary suburban home, no text, no watermark."
)
# DAY without "no text": the plate case must not forbid the text it measures.
DAY_PLATE = (
    "Photorealistic still from a fixed outdoor security camera mounted under the eaves about "
    "three meters high, wide-angle lens looking down at the scene, daytime, natural color, "
    "ordinary suburban home, no watermark."
)
DUSK = (
    "Photorealistic still from a fixed outdoor security camera mounted under the eaves about "
    "three meters high, wide-angle lens looking down at the scene, at dusk with low warm light "
    "and the porch light on, ordinary suburban home, no text, no watermark."
)
IR_NIGHT = (
    "Photorealistic still from a fixed outdoor security camera at night in infrared "
    "night-vision mode, monochrome grayscale, IR illumination with slight noise and bloom, "
    "wide-angle lens mounted under the eaves looking down, no text, no watermark."
)


@dataclass(frozen=True)
class Case:
    id: str
    scene: str
    camera: str
    owl_queries: tuple[str, ...]
    ocr_target: str | None = None

    @property
    def prompt(self) -> str:
        return f"{self.scene} {self.camera}"


CASES: tuple[Case, ...] = (
    Case(
        "handgun_in_hand",
        "A man in a dark hoodie walks up the driveway toward the front door "
        "holding a black handgun in his right hand, arm down at his side, the handgun clearly "
        "visible.",
        DAY,
        ("a handgun", "a person"),
    ),
    Case(
        "knife",
        "A person in a gray jacket stands on the front porch beside the door holding "
        "a large kitchen knife, the blade clearly visible.",
        DAY,
        ("a knife", "a person"),
    ),
    Case(
        "crowbar_at_door",
        "A person crouches at the back door prying at the door frame with a "
        "steel crowbar wedged between the door and the frame.",
        DAY,
        ("a crowbar", "a door", "a person"),
    ),
    Case(
        "balaclava_ir_night",
        "A person wearing a black balaclava ski mask that covers the "
        "whole face except the eyes walks along the side of the house.",
        IR_NIGHT,
        ("a ski mask", "a person"),
    ),
    Case(
        "forced_door",
        "The front door has been kicked in and hangs open, the door frame "
        "splintered and broken wood scattered on the porch floor.",
        DAY,
        ("a broken door", "a door"),
    ),
    Case(
        "pried_window",
        "A person in dark clothes climbs through a ground-floor window after "
        "prying it open, the window frame bent.",
        DUSK,
        ("a window", "a person"),
    ),
    Case(
        "child_alone_pool",
        "A small child about four years old stands alone at the edge of "
        "the backyard swimming pool, with no adult anywhere in view.",
        DAY,
        ("a child", "a swimming pool"),
    ),
    Case(
        "smoke_from_eave",
        "Thick gray smoke pours out from under the roof eave of the two-story house.",
        DUSK,
        ("smoke", "a house"),
    ),
    Case(
        "legible_plate",
        "A silver sedan is parked in the driveway facing the camera, its "
        "front license plate clearly readable: 8KXR-417.",
        DAY_PLATE,
        ("a license plate", "a car"),
        ocr_target="8KXR-417",
    ),
)

IDENTITY_PERSON = (
    "a man in his forties with short curly black hair, a trimmed beard, a small scar above the "
    "left eyebrow, wearing a navy windbreaker"
)
IDENTITY_REFERENCE = (
    f"Photorealistic portrait of {IDENTITY_PERSON}, standing on a front porch facing the camera, "
    "even daylight, sharp focus on the face."
)
SHOTS: tuple[str, ...] = (
    "standing on the front porch facing the camera",
    "walking up the driveway toward the camera",
    "opening the side gate",
    "at the front door in three-quarter view",
    "looking back over his shoulder toward the street",
)
LIGHTING: dict[str, str] = {"day": DAY, "dusk": DUSK, "ir_night": IR_NIGHT}


def identity_edit_prompt(shot: str, lighting: str) -> str:
    return (
        "The same man as in the reference image, with the same face, hair, beard, scar and navy "
        f"windbreaker, {shot}. {LIGHTING[lighting]}"
    )


def identity_t2i_prompt(shot: str, lighting: str) -> str:
    return f"{IDENTITY_PERSON[0].upper()}{IDENTITY_PERSON[1:]}, {shot}. {LIGHTING[lighting]}"


@dataclass(frozen=True)
class ClipCase:
    id: str
    keyframe: str  # a Case id, or "identity:<shot index>:<lighting>"
    motion: str


CLIPS: tuple[ClipCase, ...] = (
    ClipCase(
        "armed_approach",
        "handgun_in_hand",
        "The man keeps walking steadily up the "
        "driveway toward the front door, the handgun still in his hand. Fixed camera, no "
        "camera movement.",
    ),
    ClipCase(
        "pry_door",
        "crowbar_at_door",
        "The person levers the crowbar back and forth, "
        "forcing the door frame. Fixed camera, no camera movement.",
    ),
    ClipCase(
        "child_pool",
        "child_alone_pool",
        "The child takes a small step closer to the "
        "water's edge and looks down at the pool. Fixed camera, no camera movement.",
    ),
    ClipCase(
        "identity_walk",
        "identity:1:day",
        "The man walks up the driveway toward the "
        "camera and stops near the porch. Fixed camera, no camera movement.",
    ),
)

SEEDS: tuple[int, ...] = (11, 22, 33, 44)
CLIP_SEEDS: tuple[int, ...] = (11, 22)
MODEL_SIZES: dict[str, tuple[int, int]] = {
    "flux2-dev": (1920, 1088),
    "flux2-klein-4b": (1344, 768),
    "qwen-image-2.1": (1664, 928),
    "z-image-turbo": (1920, 1088),
    "hidream-i1-full": (1360, 768),
    "ideogram-4": (1920, 1088),
}
T2I_MODELS: tuple[str, ...] = tuple(MODEL_SIZES)
EDIT_MODELS: tuple[str, ...] = ("qwen-image-2.1", "flux2-dev", "flux2-klein-4b")
I2V_MODELS: tuple[str, ...] = ("ltx-2.5", "wan2.2-i2v")
# Per model: LTX-2.5's latent grid needs multiples of 32 (720 is not one).
CLIP_SIZES: dict[str, tuple[int, int]] = {"ltx-2.5": (1280, 704), "wan2.2-i2v": (1280, 720)}
# LTX-2.5 takes 8n + 1 frames, Wan 2.2 takes 4n + 1.
CLIP_FRAMES: dict[str, int] = {"ltx-2.5": 97, "wan2.2-i2v": 81}
KEYFRAME_MODEL = "flux2-dev"
KEYFRAME_SEED = 11
