#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx",
# ]
# ///
# ABOUTME: Generate promotional videos for Home Security Intelligence using NVIDIA's inference API with Veo 3.1.
# ABOUTME: Supports initial generation and extension hops to create videos up to 120 seconds.
"""
Generate promotional videos for Home Security Intelligence using Veo 3.1.

Requires NVIDIA_API_KEY or NVAPIKEY environment variable to be set.

Usage:
    # Generate all 8 videos
    uv run scripts/generate_videos.py --all

    # Generate a specific video
    uv run scripts/generate_videos.py --video 1a

    # List available videos
    uv run scripts/generate_videos.py --list

    # Test API connection with a simple prompt
    uv run scripts/generate_videos.py --test
"""

import argparse
import base64
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

# API Configuration
API_BASE_URL = "https://inference-api.nvidia.com"
VIDEO_MODEL = "gcp/google/veo-3.1-generate-001"

# Video generation settings
DEFAULT_DURATION = 8  # seconds for initial generation
EXTENSION_DURATION = 7  # seconds added per extension hop
TARGET_DURATION = 120  # target total duration in seconds
RESOLUTION = "1080p"
ASPECT_RATIO = "16:9"

# Output directory
OUTPUT_DIR = Path.home() / "Documents" / "Videos" / "HomeSecurityIntelligence"


@dataclass
class VideoPrompt:
    """A video prompt with metadata."""

    id: str
    name: str
    description: str
    prompt: str


# All 8 video prompts from the design document
VIDEO_PROMPTS: dict[str, VideoPrompt] = {
    "1a": VideoPrompt(
        id="1a",
        name="Day-to-Night Security Timelapse",
        description="Timelapse of suburban home from dawn to night with security camera perspective",
        prompt="""Subject: A contemporary two-story suburban home with clean architectural lines, painted in warm gray with white trim. The home features a concrete driveway that can fit two vehicles, a manicured front lawn with low ornamental grasses, and a covered front porch with a modern black front door. A Foscam security camera is visibly mounted under the porch eave, its lens facing the driveway. The home has large windows on the ground floor, and through one side window, a home office is partially visible containing a compact PC tower on a desk - this tower has subtle RGB lighting that glows NVIDIA green (#76B900). The property has a single mature tree providing partial shade over the lawn.

Action: The video captures a full day-to-night cycle compressed into a continuous timelapse. In the early morning, dew is visible on the grass and the porch light switches off automatically. As morning progresses, shadows from the tree sweep across the lawn. A mail carrier briefly appears mid-morning, walking to the mailbox at the curb and departing. During afternoon hours, the shadows shift dramatically, a neighborhood cat crosses the lawn, and sprinklers activate briefly in the garden beds. As golden hour approaches, the lighting becomes warm and cinematic. At dusk, the porch light activates automatically, casting a warm pool of light. The home office window begins to glow more prominently as interior lights come on, the NVIDIA green from the PC tower becoming more visible. As full darkness falls, a car's headlights sweep across the scene, pulling into the driveway. The security camera's small indicator LED pulses briefly as it detects the motion. A figure exits the car, walks to the front door, and enters the home. The porch light remains on as the scene settles into quiet nighttime stillness.

Scene/Context: A quiet residential neighborhood in a temperate climate, likely Pacific Northwest or Northern California based on the vegetation. This is an established neighborhood with similar homes visible in the soft background - not a new development, but well-maintained. The street is a low-traffic residential road. The season appears to be late spring or early summer, with full foliage on the tree and green grass. This is a safe, middle-class neighborhood where the security system represents smart home convenience rather than high-crime necessity.

Camera: Fixed wide-angle shot from the mounted Foscam security camera position - approximately 10 feet high, under the porch eave, looking outward at a slight downward angle toward the driveway and front yard. This creates the authentic security camera aesthetic with mild barrel distortion at the edges. The shot is locked off with no movement, as a real security camera would be.

Visual Style: Photorealistic cinematography with the slight degradation expected from a consumer security camera. Colors are accurate but slightly compressed in dynamic range. The timelapse compression creates smooth, hypnotic shadow movement. The overall mood is peaceful and domestic. The NVIDIA green (#76B900) appears as a subtle accent - the GPU glow through the window should be noticeable but not garish. Nighttime portions have realistic noise/grain typical of security camera sensors in low light.

Audio: Natural ambient soundscape evolving with time of day. Dawn brings birdsong - robins, sparrows. Midday includes distant neighborhood sounds: a lawnmower somewhere down the block, children playing faintly. Golden hour brings evening birds. Night is quieter - crickets, occasional distant dog bark. The arriving car has realistic engine and door sounds.""",
    ),
    "1b": VideoPrompt(
        id="1b",
        name="Night Arrival Sequence",
        description="Nighttime security footage of resident arriving home with AI overlay",
        prompt="""Subject: A single-story ranch-style home in a suburban setting, painted in muted earth tones with a two-car garage and a concrete driveway extending approximately 40 feet from the street. The garage has small windows at the top of each door, and through the left garage window, the interior is partially visible - a workbench area with a compact home server rack containing an NVIDIA GPU that emits a soft, pulsing green glow (#76B900). A Foscam security camera is mounted at the corner where the garage meets the main house, positioned to capture the full driveway and the path to the front door. The front yard has mature landscaping - two small Japanese maples and ground cover that appears silver-green under the security lighting. A motion-sensor floodlight is mounted above the garage. The front door is recessed under a small portico with a warm-toned porch light. A late-model Honda Accord or similar practical sedan will be the arriving vehicle.

Action: The video opens on a quiet, still nighttime scene - the home is peaceful, porch light on, garage dark except for the faint green GPU glow visible through the small window. For the first portion, very little moves except perhaps a moth circling the porch light and tree leaves rustling gently. Then, at the far end of the frame, headlights appear on the street, growing brighter as the car approaches. The vehicle slows, turn signal blinking, and pulls into the driveway. The motion-sensor floodlight above the garage activates, bathing the driveway in bright white light. The car comes to a stop, engine turns off, headlights extinguish. A pause, then the driver's door opens and the dome light illuminates the interior briefly. A woman in her 30s or 40s exits, wearing business casual clothing - she's returning from work. She reaches into the back seat and retrieves two canvas grocery bags. She closes the car door with her hip, clicks the key fob (taillights flash twice), and walks along the path toward the front door. As she walks, a subtle UI overlay fades into the corner of the frame: first "Processing locally..." in a clean sans-serif font with a small loading animation, then this transitions to "Risk: 12 - Resident identified" with a small green checkmark. The text uses NVIDIA green (#76B900) as the accent color. The woman reaches the front door, shifts the grocery bags to enter a code on a keypad, and enters the home. The front door closes behind her. The motion-sensor light remains on for another few seconds, then clicks off, returning the scene to the quiet porch-light-only illumination. The green GPU glow continues to pulse gently in the garage window.

Camera: Fixed security camera perspective from the corner-mounted Foscam position, approximately 9 feet high, angled to capture the full driveway from garage to street, the walkway to the front door, and the front entrance itself. The lens is wide-angle, creating the characteristic security camera look with mild distortion toward the edges of frame. There is no camera movement - the shot is completely locked off.

Visual Style: Photorealistic nighttime security camera footage with authentic characteristics of consumer-grade equipment: slightly elevated noise/grain in the darker areas, good but not perfect dynamic range, accurate but somewhat muted colors. The UI overlay elements should feel integrated but clearly artificial - clean, vector-based graphics. Typography is clean and modern, using NVIDIA green (#76B900) for accent elements with white text for readability.

Audio: Realistic nighttime suburban soundscape. Crickets, the gentle hum of the porch light, perhaps a distant dog barking once. Car engine sound grows from faint to present. Turn signal clicking audible. Car door opens with realistic latch sound. Door closes with solid thunk. Key fob chirp. Footsteps on concrete. Subtle soft chime when displaying "Resident identified". Keypad beeps. Door opens and closes.""",
    ),
    "4a": VideoPrompt(
        id="4a",
        name="Dawn Property Flyover Tour",
        description="Cinematic drone flyover of smart home at dawn revealing security coverage",
        prompt="""Subject: A modern farmhouse-style home with contemporary elements - white board-and-batten siding, black metal roof, large black-framed windows, and a wraparound porch. The property sits on approximately half an acre in a semi-rural or large-lot suburban setting. The home is two stories with an attached two-car garage. Security cameras are integrated thoughtfully into the architecture: one under each eave at the corners (four total), one above the garage, and one covering the back patio - they should be visible but not obtrusive, suggesting professional installation. The backyard features a covered patio with outdoor furniture, a small lawn area, a vegetable garden in raised beds, and a detached workshop or studio building. A gravel path connects the main house to the workshop. Through the large windows of what appears to be a home office on the ground floor, a desk setup is visible with a compact workstation featuring NVIDIA GPU lighting in green (#76B900). The front of the property has a circular driveway with landscaped center island, mature trees providing partial canopy, and a flagstone walkway to the front door. The front door has a small smart doorbell camera and a subtle LED status indicator that glows NVIDIA green.

Action: The video begins with the drone positioned high above the property at dawn, the home small in frame with the surrounding landscape visible - neighboring properties at a distance, perhaps a tree line or gentle hills in the background. Morning mist hovers low over the grass, catching the early golden light. The drone begins a slow, graceful descent while simultaneously beginning to orbit the property clockwise. As it descends and circles, different aspects of the home and security coverage are revealed: the front approach with driveway camera coverage, the side yard with its gate and corner camera, the backyard with patio camera overlooking the outdoor living space, the workshop with its own small camera above the door. The descent continues, bringing the drone lower and closer to the structure. A segment of the flight passes close to the home office window, clearly revealing the glowing green GPU inside the workstation. The orbit continues to the front of the home, where the drone descends to approximately eye level with the front door, slowly approaching. The smart doorbell camera is clearly visible, and the small LED status indicator beside the door glows steady NVIDIA green, suggesting the system is active and healthy. The final moments hold on this front door view, the home office window visible to the side with its green glow.

Camera: Smooth, professional drone cinematography in the style of high-end real estate videography or architectural documentation. The movement is continuous and flowing - no abrupt changes or jerky corrections. The primary motion is a descending spiral: the drone loses altitude steadily while orbiting the property clockwise. Gimbal movements are subtle and purposeful, occasionally tilting down slightly to emphasize ground features or tilting up to show the roofline and cameras. The overall feeling should be graceful and almost meditative.

Visual Style: Cinematic drone footage with professional architectural videography characteristics: smooth motion, rich colors, careful attention to golden hour lighting. The morning light creates long shadows, warm highlights, and a sense of new-day optimism. The mist adds production value and atmosphere. Colors are saturated but natural. The NVIDIA green (#76B900) appears in the GPU glow through the office window and the front door status LED. The overall mood is aspirational and peaceful.

Audio: Immersive dawn soundscape emphasizing the peaceful, natural setting. Birds are prominent - a dawn chorus of songbirds. The drone itself should be nearly or completely silent - this is cinematic representation. Gentle ambient wind, the rustle of leaves in the tree canopy. As the drone descends lower, more intimate sounds become audible: the gentle drip of dew from leaves, perhaps a wind chime on the back patio. No music - the natural soundscape is the score.""",
    ),
    "4b": VideoPrompt(
        id="4b",
        name="Neighborhood Context to Smart Home",
        description="Aerial journey down a suburban street arriving at smart home with text overlays",
        prompt="""Subject: A tree-lined residential street in an established suburban neighborhood, featuring a mix of home styles from the 1990s to 2010s - craftsman influences, traditional two-stories, some contemporary updates. Mature trees create a canopy over the street. The neighborhood is well-maintained but lived-in - basketball hoops in some driveways, kids' bikes visible, varied landscaping reflecting individual homeowner choices. One home, positioned mid-block, stands out subtly as the "smart home" - a recently renovated craftsman with clean landscaping, a modern electric vehicle in the driveway, and small but visible security cameras integrated into the design. This is not a mansion or a tech compound - it's an ordinary home that happens to be thoughtfully upgraded. Through the front window of this home, a home office setup is visible with a small tower PC or mini-ITX build glowing NVIDIA green (#76B900). The front porch has a modern video doorbell, and a subtle status LED near the door glows the same green.

Action: The video opens with a high, wide aerial shot of the neighborhood at sunrise - multiple blocks visible, establishing this as a normal residential area. The drone begins slowly pushing forward and descending, moving down the tree-lined street as if traveling along it. Morning activity is visible: a jogger on the sidewalk, someone in a robe retrieving a newspaper, a car backing out of a driveway headed to work. The push continues, the camera gradually centering on the smart home as it becomes clear this is the destination. Text fades in smoothly: "Edge AI Security" in clean white typography, positioned in the upper portion of the frame. As the drone continues its approach, descending to street level, additional text appears below: "No cloud required" - this line uses NVIDIA green (#76B900) for emphasis. The neighborhood context remains visible - other homes, the tree canopy, the normal suburban environment - but the smart home is now clearly the subject. The final portion of the video brings the drone to a hover at the edge of the property, looking at the home from the street perspective a potential visitor would have. The security cameras are visible but unobtrusive. The green glow from the home office window is clear. The status LED by the front door pulses gently.

Camera: Cinematic drone flight that functions as a traveling shot down the street. The opening is high and wide - establishing the neighborhood geography. The primary movement is a push forward combined with gradual descent, as if the drone is flying down the street at decreasing altitude. The camera maintains a primarily forward-facing angle but makes subtle adjustments to keep points of interest framed well. The final hover provides a stable frame for the text overlays.

Visual Style: Warm, inviting cinematography that presents the neighborhood as an aspirational but attainable place to live. The sunrise lighting creates long shadows and golden highlights. The image is clean and professional but not over-produced. Colors are warm and natural. The text overlays use clean, modern typography - premium tech company style but not flashy. The NVIDIA green (#76B900) is used sparingly: the "No cloud required" text, the GPU glow through the window, the status LED. The overall mood is optimistic and empowering.

Audio: Layered soundscape evolving with the drone's journey. Opening high shot has ambient, less distinct sound - wind at altitude, distant neighborhood sounds blended together. As the drone descends, sounds become more specific: birds singing, the jogger's footsteps, the thump of the newspaper landing on a porch, a car engine starting. A subtle, almost subliminal musical element could be introduced in the final section - a soft, electronic tone that suggests technology and security without being aggressive.""",
    ),
    "2a": VideoPrompt(
        id="2a",
        name="AI Processing Data Visualization Journey",
        description="Abstract visualization of the AI security pipeline processing data",
        prompt="""Subject: An abstract visualization representing the Home Security Intelligence system's data processing pipeline, rendered in a dark, sophisticated environment reminiscent of high-end technology interfaces. The visualization exists in a three-dimensional space - not flat UI, but volumetric data representations floating in a void. The core elements include: raw camera feed panels (rectangular, showing actual security footage), neural network node clusters (spherical nodes connected by glowing pathways), detection highlight frames (bounding boxes that materialize and pulse), risk assessment gauges (circular or arc-shaped meters filling with color), and alert dispatch visualizations (data packets traveling along pathways to endpoint icons representing phones, dashboards, and notification systems). The color palette is predominantly dark - deep blue-blacks and charcoal grays - with NVIDIA green (#76B900) as the primary accent color for active elements, data flows, and highlights. Secondary accents include white for text and UI elements, and subtle amber/orange for alert-state indicators. The Nemotron v3 Nano branding appears as a central element - perhaps a stylized logo or text treatment that serves as the "brain" at the center of the processing visualization. Throughout the piece, small text elements reinforce the edge AI message: "Local Processing", "No Cloud Upload", "Privacy Preserved", "< 50ms Latency".

Action: The video opens in darkness, then a single point of NVIDIA green light appears at center, pulsing gently like a heartbeat. This expands into the Nemotron v3 Nano wordmark or logo, establishing the star of the system. From this central point, the visualization begins to build outward. First, camera feed panels materialize around the periphery - four to six rectangular frames showing different angles of a home. Lines of green energy connect these feeds to the central Nemotron core, representing data flowing inward. As the data flows reach the center, neural network visualizations activate - clusters of nodes lighting up in cascading patterns, suggesting deep learning inference in progress. The visualization zooms or transitions to show this processing in more detail: layers of a neural network illuminating sequentially, weights and activations represented as flowing particles. Detection events emerge from this processing - bounding boxes materialize on the camera feeds, highlighting a person in one frame, a vehicle in another. These detections flow as data packets back toward the center, where risk assessment begins. A prominent gauge visualization shows risk scores being calculated - numbers ticking up, the meter filling, finally settling on a value (e.g., "Risk: 34 - Normal Activity"). For comparison, another assessment shows a higher risk event with the meter climbing higher and shifting toward amber ("Risk: 78 - Unknown Visitor"). Finally, alert dispatch is visualized: data packets streaming outward from the core to endpoint icons. The visualization completes with a pull-back to show the entire system operating in harmony. Text fades in: "Nemotron v3 Nano" prominently, with "Edge AI for Everyone" below.

Camera: The camera exists within this abstract 3D space and moves fluidly through it. The opening is a slow push toward the emerging central light. As the visualization builds, the camera pulls back to reveal scope, then pushes in to examine details. Movement is smooth and continuous, with no cuts - this is a single flowing journey. The camera occasionally orbits elements to show dimensionality. Depth of field is used intentionally. The final pull-back is expansive, rising up and away to show the complete system.

Visual Style: Premium technology visualization with cinematic production values. The dark environment allows glowing elements to pop dramatically. The NVIDIA green (#76B900) dominates as the "healthy system" color. The green should feel energetic but not aggressive - more "life force" than "matrix code." Particle effects add richness: data isn't just lines, it's streams of small particles flowing along paths. Neural network activations ripple and cascade. Typography is clean, modern, and highly legible - a sans-serif font family. The overall mood is confident, sophisticated, and cutting-edge.

Audio: Designed sound that reinforces technological sophistication without feeling like generic sci-fi. The opening pulse has a deep, resonant tone - almost like a heartbeat but synthetic. As elements materialize, each has a subtle audio signature: camera feeds have soft digital "appearance" sounds, neural network nodes have gentle chimes or tones that cascade, data flows have smooth whooshing quality. The risk assessment gauge filling could have a rising tone. Alert dispatches have satisfying "send" sounds. Underlying everything is a subtle ambient pad - electronic, warm. The Nemotron branding reveal has a slightly more prominent audio moment.""",
    ),
    "2b": VideoPrompt(
        id="2b",
        name="System Boot Sequence",
        description="Cinematic visualization of the AI security system initializing",
        prompt="""Subject: A visualization of the Home Security Intelligence system initializing from cold start to full operation, presented as a cinematic "boot sequence" that reveals the architecture and capabilities of the platform. The visual environment is a hybrid of abstract data space and stylized hardware representation - we see both the physical components (GPU, cameras, server) rendered as glowing wireframe or holographic objects, and the software systems they run rendered as data visualizations connecting them. The NVIDIA GPU is prominently featured as the computational heart - rendered beautifully with accurate geometry, its fans beginning to spin, RGB lighting activating in NVIDIA green (#76B900). The Nemotron v3 Nano model is visualized as a complex neural architecture that "loads" into the GPU - layers and parameters streaming in. Camera feeds appear as floating panels that come online one by one. The central dashboard interface materializes as the final element, showing that the system is ready to protect. Text elements throughout reinforce the technology stack: "NVIDIA RTX", "Nemotron v3 Nano", "RT-DETRv2", "Local Processing", "Edge AI Ready".

Action: The video opens in complete darkness with silence. A moment of stillness, then a single spark - the press of a power button, visualized as a small circle of green light. This spark travels along circuit traces, visualized as glowing pathways, toward the GPU. The GPU materializes from darkness - first as a wireframe outline, then filling in with detail. Its fans begin to spin, slowly at first, then reaching operational speed. The RGB lighting activates in NVIDIA green, and the GPU pulses with readiness. Text appears: "NVIDIA RTX Initialized." From the GPU, energy flows outward along data pathways to other components. A compact server or mini-PC chassis materializes, its internal components visible in stylized cross-section. Storage systems activate - visualized as data blocks lighting up sequentially. "Storage Online." Memory modules initialize with cascading light patterns. "32GB Memory Ready." The most dramatic sequence follows: the Nemotron v3 Nano model loading. This is visualized as an immense neural architecture - billions of parameters represented as a vast, intricate structure - streaming from storage through memory into the GPU. The architecture fills and illuminates section by section, each layer activating with a pulse of green light. "Nemotron v3 Nano Loaded - 4B Parameters." The RT-DETRv2 detection model loads similarly but more quickly - a smaller but precise architecture snapping into place. "RT-DETRv2 Detection Ready." Now the cameras come online: panels appear around the periphery, each one flickering from static to a clear image as its feed initializes. Four, five, six cameras activating in sequence, each with a small "Camera 01 Online" indicator. Finally, the dashboard interface materializes at the center - a clean, modern UI showing camera thumbnails, status indicators, and the message: "System Ready - Protecting Your Home." The visualization settles into an operational state.

Camera: The camera is intimate with the hardware during initialization sequences, pulling back to show software and system-level visualizations. Opening shot is tight on the power button spark, then follows the energy flow to the GPU. The GPU materialization is shot with reverence - slow orbit around the card as it appears and activates. During the Nemotron loading sequence, the camera pushes into the neural architecture, flying through layers and connections. The final dashboard materialization is shot straight-on, like a user sitting in front of their command center. Movement throughout is smooth and purposeful.

Visual Style: Hardware components are rendered in a stylized manner - accurate enough to be recognizable but enhanced with holographic wireframe effects, glowing edges, and visible energy flows. The aesthetic is "technical illustration come to life." The color palette is dark with NVIDIA green (#76B900) as the primary accent, plus blue for memory, amber for storage, white for text and UI elements. The neural network visualizations should be genuinely impressive - conveying the scale of billions of parameters through visual density and intricacy. Particle effects are used extensively. Typography follows clean sans-serif principles.

Audio: Boot sequence sound design that enhances the technical atmosphere. The opening power button press has a satisfying click and electronic initiation tone. The spark traveling along circuit traces has a subtle electrical crackle. The GPU initializing has layered sounds: fans spinning up (rising whoosh), power delivery engaging (deep hum), RGB lighting activating (gentle chime). Each component initialization has its own audio signature. The Nemotron loading sequence is the audio centerpiece - a building, layered sound that conveys massive data transfer. The final dashboard appearance has a confident "ready" tone.""",
    ),
    "3a": VideoPrompt(
        id="3a",
        name="Real-Time Detection Event with AI Overlay",
        description="Security camera footage with live AI analysis overlay demonstrating detection",
        prompt="""Subject: A realistic security camera view of a backyard at dusk, with AI analysis overlay appearing in real-time to demonstrate the detection and assessment capabilities of the system. The scene is a typical suburban backyard: wooden privacy fence, patio with outdoor furniture, a grill, perhaps a small lawn area and garden beds, and a back door with a motion-sensor light. The camera is mounted at the corner of the house, angled to cover the full backyard and the back entrance. The scene begins as normal security footage, then transforms as the AI overlay materializes - bounding boxes appearing around detected objects, tracking indicators following movement, confidence percentages displaying, and ultimately a risk assessment score calculating and displaying. The overlay aesthetic is clean and modern, using NVIDIA green (#76B900) for detection boxes around known/safe elements and amber/orange for unknown or elevated-risk elements. Text overlays show the system's analysis: object classifications ("Person", "Outdoor Furniture", "Grill"), confidence levels ("98%", "94%"), tracking IDs ("ID: 001"), and the final risk assessment ("Risk: 67 - Unknown Individual"). A processing indicator shows that all analysis is happening locally: "Processing: Local | Latency: 43ms | No Cloud Upload."

Action: The video opens on the quiet backyard scene - no movement, dusk lighting, peaceful. The motion-sensor light is off. Ambient activity only: a bird hopping on the fence, leaves rustling. Then, movement: a figure appears at the side gate, opening it and entering the backyard. The motion-sensor light activates, illuminating the scene. The AI overlay begins to materialize. First, a subtle scanning effect washes across the frame - a horizontal line or grid suggesting the AI is analyzing the image. Detection boxes begin to appear: first around static objects (furniture, grill) in NVIDIA green with low-opacity fills. Then, the critical detection: a bounding box appears around the person, initially amber/yellow indicating "analyzing." The box tracks the person's movement smoothly as they walk across the backyard. A classification label appears: "Person - Confidence: 97%". A tracking ID assigns: "ID: 001". The system attempts identification - a brief "Identifying..." indicator, then the result: "Unknown Individual" (this isn't a registered household member). The risk assessment calculation becomes visible - a gauge or meter in the corner of the frame, filling and calculating based on multiple factors. Contributing factors briefly display: "Time: Dusk (+5)", "Location: Backyard (+3)", "Identity: Unknown (+25)", "Behavior: Walking toward door (+10)". The final score resolves: "Risk: 67 - Unknown Individual - Alert Recommended". An alert notification visualization appears. The person reaches the back door and... produces a key, entering the home. The system updates: "Door Entry Detected - Re-evaluating..." then "Registered Entry Code Used - Risk Adjusted: 15 - Returning Resident (New Pattern)". The overlay indicates the system is learning. A final status display: "Nemotron v3 Nano | Local Processing | Learning Enabled."

Camera: Fixed security camera perspective throughout - authentic footage from a mounted Foscam-style camera at approximately 8 feet height, angled down at roughly 30 degrees to cover the backyard. The wide-angle lens creates mild barrel distortion at the edges. There is no camera movement; the scene is captured exactly as a real security camera would capture it. All dynamism comes from movement within the frame and the AI overlay elements.

Visual Style: The base footage should look like authentic, high-quality consumer security camera output: good resolution but with characteristics of a security sensor - slightly elevated noise in the shadows, reasonable but not cinematic dynamic range. The AI overlay creates a deliberate contrast: clean, vector-based graphics layered over the footage. Bounding boxes are crisp with rounded corners and subtle fills. Color coding is consistent: NVIDIA green (#76B900) for known/safe elements, amber (#F5A623) for unknown/analyzing.

Audio: Realistic backyard ambient audio. Opening quiet: crickets beginning their evening chorus, distant neighborhood sounds, leaves rustling. When the gate opens: the creak and click of a wooden gate latch, footsteps on grass. Motion light: a subtle click when it activates. The AI overlay elements have restrained audio design - subtle indicators that enhance the experience. Detection box appearances have quiet, professional "lock on" tones. The risk assessment calculating could have subtle computational sounds. The final "Alert Recommended" has a soft chime. When the system re-evaluates, a different, more resolved tone.""",
    ),
    "3b": VideoPrompt(
        id="3b",
        name="Multi-Camera Security Montage with AI Analysis",
        description="Montage cycling through multiple camera feeds with AI overlay",
        prompt="""Subject: A dynamic montage cycling through multiple security camera feeds around a home, each showing the AI analysis overlay in action across different scenarios and times of day. The cameras include: front door/porch cam, driveway cam, backyard cam, side gate cam, garage interior cam, and a wide establishing cam showing the front of the property. Each feed shows different activity appropriate to its location: package delivery at the front door, car arriving in the driveway, children playing in the backyard, a neighbor waving at the side gate, the homeowner in the garage workshop (with the NVIDIA GPU-equipped server visible in the corner, its green glow prominent). Every scene includes the AI overlay showing real-time analysis: bounding boxes, object classifications, person identification (family members show names), activity recognition, and risk assessments. A persistent UI element shows which camera is currently displayed, system status, and the Nemotron v3 Nano branding. Family members are identified by name with green bounding boxes. Known visitors are green with a "known" badge. The final summary shows: "All Cameras Active | 6 Family Members Home | 0 Alerts | System Healthy."

Action: The video opens with a camera selection interface - a grid showing all six camera feeds as thumbnails, suggesting the dashboard a user would see. A selection highlight moves to the first camera (front door) and the view transitions to full-screen on that feed. The front door camera shows a package delivery in progress: a delivery person approaches, places a package, rings the doorbell, and departs. The AI overlay identifies them ("Delivery Person - Confidence: 95%"), tracks their movement, recognizes the package ("Package Detected - Amazon"), and assesses low risk ("Risk: 8"). A notification preview shows: "Front Door: Package Delivered." Smooth transition to the driveway camera, where a family car is arriving. The AI tracks the vehicle ("2022 Honda CR-V - Registered"), waits for the driver to exit, identifies them ("Dad - Family Member"), and shows welcoming low risk ("Risk: 3 - Welcome Home"). The backyard camera shows children playing - the AI has identified them ("Emma, 8" and "Lucas, 5") with green bounding boxes, tracking their movement playfully. Risk is minimal ("Risk: 2 - Supervised Play"). When a ball goes over the fence, the AI notes the event but doesn't escalate. The side gate camera shows a neighbor approaching and waving toward the camera. The AI identifies them ("Maria - Known Neighbor") and assesses appropriately ("Risk: 5 - Known Visitor"). The garage camera shows the homeowner at a workbench, with the NVIDIA GPU-equipped server visible in the corner, its green glow prominent. The AI identifies the owner ("Mom - Primary User") with ultra-low risk. Finally, the establishing camera shows the full front of the home as evening approaches - a peaceful scene with multiple family members visible through windows, cars in the driveway, all identified and accounted for. A final summary overlay appears: "All Cameras Active | 6 Family Members Home | 0 Alerts | System Healthy." The Nemotron v3 Nano branding is prominent, with the tagline: "Your Home, Understood."

Camera: Each camera feed maintains its authentic fixed-perspective security camera aesthetic - these are real camera positions showing real footage, not cinematic shots. The visual variety comes from the different camera placements: door cam is at doorbell height, driveway cam is mounted on the garage, backyard cam is elevated, side gate cam is at fence height, garage cam is corner-mounted inside, and the establishing cam is positioned across the street or at the property edge. Transitions between cameras use clean motion design: perhaps a brief return to the grid view, or smooth animated transitions with camera labels.

Visual Style: Each camera feed has the authentic security camera look appropriate to its position - consumer-grade but good quality. The AI overlay is consistent across all feeds: same font family, same color coding, same UI element styling. NVIDIA green (#76B900) is used throughout for positive identifications and low-risk assessments. Family member names appear in green with small profile icon indicators. The persistent UI showing camera name and system status uses a semi-transparent dark background. The final summary screen is a satisfying dashboard view. The Nemotron branding is clear but not overwhelming.

Audio: Each camera feed has appropriate ambient audio for its location: front door has doorbell sound and delivery person's "Package for you!"; driveway has car engine, door closing, footsteps; backyard has children laughing and playing; side gate has friendly greeting exchange; garage has workshop sounds plus the hum of the server; establishing shot has evening neighborhood ambience. AI overlay sounds are consistent across all feeds - the same subtle detection tones, identification confirmations, and status sounds. Transitions between cameras could have a soft interface sound. The final summary screen could have a slightly more prominent musical element - a few notes suggesting "all is well." """,
    ),
}


def get_api_key() -> str:
    """Get the NVIDIA API key from environment variables."""
    api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVAPIKEY")
    if not api_key:
        print(
            "Error: NVIDIA_API_KEY or NVAPIKEY environment variable not set",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key


def get_output_dir() -> Path:
    """Get the output directory, creating it if necessary."""
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True, mode=0o755)
    return OUTPUT_DIR


def save_video(video_data: bytes, output_path: Path) -> Path:
    """Save video data to a file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(video_data)
    return output_path


def generate_video_initial(
    client: httpx.Client,
    prompt: str,
    duration: int = DEFAULT_DURATION,
    resolution: str = RESOLUTION,
    aspect_ratio: str = ASPECT_RATIO,
) -> dict:
    """
    Generate an initial video using Veo 3.1.

    This function attempts multiple API formats since the exact NVIDIA format
    may differ from the standard Google API.
    """
    api_key = get_api_key()

    # Try different API formats
    api_formats = [
        # Format 1: Simple JSON body (based on user's example)
        {
            "url": f"{API_BASE_URL}/v1/video/generations",
            "json": {
                "model": VIDEO_MODEL,
                "prompt": prompt,
                "seconds": str(duration),
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
            },
        },
        # Format 2: OpenAI-compatible chat completions style
        {
            "url": f"{API_BASE_URL}/v1/chat/completions",
            "json": {
                "model": VIDEO_MODEL,
                "messages": [{"role": "user", "content": f"Generate a video: {prompt}"}],
                "max_tokens": 4096,
            },
        },
        # Format 3: Direct model endpoint
        {
            "url": f"{API_BASE_URL}/v1/models/{VIDEO_MODEL}/generate",
            "json": {
                "prompt": prompt,
                "duration_seconds": duration,
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
            },
        },
        # Format 4: Vertex AI style
        {
            "url": f"{API_BASE_URL}/v1/video/generate",
            "json": {
                "model": VIDEO_MODEL,
                "instances": [{"prompt": prompt}],
                "parameters": {
                    "durationSeconds": duration,
                    "resolution": resolution,
                    "aspectRatio": aspect_ratio,
                    "sampleCount": 1,
                },
            },
        },
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    last_error = None
    for i, api_format in enumerate(api_formats, 1):
        print(f"  Trying API format {i}/{len(api_formats)}...")
        try:
            response = client.post(
                api_format["url"],
                json=api_format["json"],
                headers=headers,
                timeout=300.0,  # 5 minute timeout for video generation
            )

            if response.status_code == 200:
                print(f"  Success with format {i}!")
                return {
                    "success": True,
                    "format_used": i,
                    "response": response.json(),
                    "request": api_format,
                }
            else:
                last_error = {
                    "format": i,
                    "status_code": response.status_code,
                    "response": response.text,
                    "request": api_format,
                }
                print(f"  Format {i} returned status {response.status_code}")

        except httpx.RequestError as e:
            last_error = {"format": i, "error": str(e), "request": api_format}
            print(f"  Format {i} failed with error: {e}")

    # All formats failed - return debug info
    return {
        "success": False,
        "last_error": last_error,
        "message": "All API formats failed. Please check the API documentation.",
    }


def extend_video(
    client: httpx.Client,
    video_data: bytes,
    prompt: str,
    extension_duration: int = EXTENSION_DURATION,
) -> dict:
    """
    Extend an existing video by generating a continuation.

    This uses the video extension feature to add more seconds to an existing video.
    """
    api_key = get_api_key()

    # Encode video as base64
    video_base64 = base64.b64encode(video_data).decode("utf-8")

    # Try extension formats
    api_formats = [
        # Format 1: Video extension endpoint
        {
            "url": f"{API_BASE_URL}/v1/video/extend",
            "json": {
                "model": VIDEO_MODEL,
                "video": f"data:video/mp4;base64,{video_base64}",
                "prompt": prompt,
                "seconds": str(extension_duration),
            },
        },
        # Format 2: Generation with video input
        {
            "url": f"{API_BASE_URL}/v1/video/generations",
            "json": {
                "model": VIDEO_MODEL,
                "prompt": prompt,
                "input_video": f"data:video/mp4;base64,{video_base64}",
                "seconds": str(extension_duration),
            },
        },
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    last_error = None
    for i, api_format in enumerate(api_formats, 1):
        print(f"  Trying extension format {i}/{len(api_formats)}...")
        try:
            response = client.post(
                api_format["url"],
                json=api_format["json"],
                headers=headers,
                timeout=300.0,
            )

            if response.status_code == 200:
                print(f"  Extension success with format {i}!")
                return {
                    "success": True,
                    "format_used": i,
                    "response": response.json(),
                }
            else:
                last_error = {
                    "format": i,
                    "status_code": response.status_code,
                    "response": response.text,
                }
                print(f"  Extension format {i} returned status {response.status_code}")

        except httpx.RequestError as e:
            last_error = {"format": i, "error": str(e)}
            print(f"  Extension format {i} failed with error: {e}")

    return {
        "success": False,
        "last_error": last_error,
        "message": "All extension formats failed.",
    }


def extract_video_from_response(response: dict) -> bytes | None:
    """Extract video data from API response."""
    # Try different response formats

    # Format 1: Direct base64 video
    if "video" in response:
        video_data = response["video"]
        if video_data.startswith("data:video"):
            # Extract base64 from data URI
            _, base64_data = video_data.split(",", 1)
            return base64.b64decode(base64_data)
        else:
            return base64.b64decode(video_data)

    # Format 2: Nested in data
    if "data" in response and isinstance(response["data"], list):
        for item in response["data"]:
            if "video" in item:
                return base64.b64decode(item["video"])
            if "b64_json" in item:
                return base64.b64decode(item["b64_json"])

    # Format 3: Nested in predictions
    if "predictions" in response:
        for pred in response["predictions"]:
            if "video" in pred:
                return base64.b64decode(pred["video"])

    # Format 4: OpenAI-style response
    if "choices" in response:
        for choice in response["choices"]:
            message = choice.get("message", {})
            content = message.get("content", "")
            # Check for base64 video in content
            if "data:video" in content:
                import re

                match = re.search(r"data:video/\w+;base64,([A-Za-z0-9+/=]+)", content)
                if match:
                    return base64.b64decode(match.group(1))

    return None


def generate_full_video(
    video_id: str,
    target_duration: int = TARGET_DURATION,
    save_intermediate: bool = True,
) -> Path | None:
    """
    Generate a full-length video with extension hops.

    Args:
        video_id: The ID of the video prompt to use (e.g., "1a", "2b")
        target_duration: Target duration in seconds
        save_intermediate: Whether to save intermediate video files

    Returns:
        Path to the final video file, or None if generation failed
    """
    if video_id not in VIDEO_PROMPTS:
        print(f"Error: Unknown video ID '{video_id}'", file=sys.stderr)
        print(f"Available videos: {', '.join(VIDEO_PROMPTS.keys())}", file=sys.stderr)
        return None

    video_prompt = VIDEO_PROMPTS[video_id]
    output_dir = get_output_dir()

    print(f"\n{'=' * 60}")
    print(f"Generating: {video_prompt.name}")
    print(f"Target duration: {target_duration} seconds")
    print(f"{'=' * 60}\n")

    with httpx.Client() as client:
        # Step 1: Generate initial video
        print(f"Step 1: Generating initial {DEFAULT_DURATION}-second video...")
        result = generate_video_initial(
            client,
            video_prompt.prompt,
            duration=DEFAULT_DURATION,
        )

        if not result["success"]:
            print("\nInitial generation failed!")
            print("Debug info:")
            print(json.dumps(result, indent=2, default=str))

            # Save debug info
            debug_path = output_dir / f"{video_id}_debug.json"
            debug_path.write_text(json.dumps(result, indent=2, default=str))
            print(f"\nDebug info saved to: {debug_path}")
            return None

        # Extract video data
        video_data = extract_video_from_response(result["response"])
        if video_data is None:
            print("\nCould not extract video from response!")
            print("Response structure:")
            print(json.dumps(result["response"], indent=2, default=str)[:2000])
            return None

        current_duration = DEFAULT_DURATION
        print(f"Initial video generated: {current_duration} seconds")

        # Save intermediate if requested
        if save_intermediate:
            intermediate_path = output_dir / f"{video_id}_initial.mp4"
            save_video(video_data, intermediate_path)
            print(f"Saved intermediate: {intermediate_path}")

        # Step 2: Extend video until target duration
        extension_count = 0
        while current_duration < target_duration:
            extension_count += 1
            print(
                f"\nStep {extension_count + 1}: Extending video "
                f"({current_duration}s -> {current_duration + EXTENSION_DURATION}s)..."
            )

            result = extend_video(client, video_data, video_prompt.prompt)

            if not result["success"]:
                print(f"Extension failed at {current_duration} seconds")
                print("Saving current progress...")
                break

            new_video_data = extract_video_from_response(result["response"])
            if new_video_data is None:
                print("Could not extract extended video from response")
                break

            video_data = new_video_data
            current_duration += EXTENSION_DURATION

            # Save intermediate
            if save_intermediate:
                intermediate_path = output_dir / f"{video_id}_ext{extension_count}.mp4"
                save_video(video_data, intermediate_path)
                print(f"Saved intermediate: {intermediate_path}")

            # Brief pause between extensions
            time.sleep(2)

        # Save final video
        final_path = output_dir / f"{video_id}_{video_prompt.name.lower().replace(' ', '_')}.mp4"
        save_video(video_data, final_path)
        print(f"\nFinal video saved: {final_path}")
        print(f"Final duration: {current_duration} seconds")

        return final_path


def test_api_connection() -> bool:
    """Test the API connection with a simple request."""
    print("Testing API connection...")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Model: {VIDEO_MODEL}")

    with httpx.Client() as client:
        result = generate_video_initial(
            client,
            "A simple test: blue sky with white clouds",
            duration=4,  # Shortest duration for testing
        )

        if result["success"]:
            print("\nAPI connection successful!")
            print(f"Working format: {result['format_used']}")
            return True
        else:
            print("\nAPI connection test failed.")
            print("Debug information:")
            print(json.dumps(result, indent=2, default=str))
            return False


def list_videos() -> None:
    """List all available video prompts."""
    print("\nAvailable Videos:")
    print("=" * 60)
    for video_id, video in VIDEO_PROMPTS.items():
        print(f"\n  {video_id}: {video.name}")
        print(f"      {video.description}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Generate promotional videos for Home Security Intelligence using Veo 3.1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test API connection
  %(prog)s --test

  # List available videos
  %(prog)s --list

  # Generate a specific video
  %(prog)s --video 1a

  # Generate all videos
  %(prog)s --all

  # Generate with custom duration
  %(prog)s --video 2a --duration 60
""",
    )
    parser.add_argument(
        "--video",
        "-v",
        help="Video ID to generate (e.g., 1a, 2b)",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Generate all 8 videos",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available video prompts",
    )
    parser.add_argument(
        "--test",
        "-t",
        action="store_true",
        help="Test API connection",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=TARGET_DURATION,
        help=f"Target duration in seconds (default: {TARGET_DURATION})",
    )
    parser.add_argument(
        "--no-intermediate",
        action="store_true",
        help="Don't save intermediate video files",
    )

    args = parser.parse_args()

    if args.list:
        list_videos()
        return

    if args.test:
        success = test_api_connection()
        sys.exit(0 if success else 1)

    if args.all:
        print(f"Generating all {len(VIDEO_PROMPTS)} videos...")
        results = []
        for video_id in VIDEO_PROMPTS:
            path = generate_full_video(
                video_id,
                target_duration=args.duration,
                save_intermediate=not args.no_intermediate,
            )
            results.append((video_id, path))

        print("\n" + "=" * 60)
        print("Generation Summary:")
        print("=" * 60)
        for video_id, path in results:
            status = "SUCCESS" if path else "FAILED"
            print(f"  {video_id}: {status}")
            if path:
                print(f"       {path}")
        return

    if args.video:
        generate_full_video(
            args.video,
            target_duration=args.duration,
            save_intermediate=not args.no_intermediate,
        )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
