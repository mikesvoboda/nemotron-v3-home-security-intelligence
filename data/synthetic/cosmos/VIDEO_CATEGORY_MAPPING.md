# Cosmos Video Category Mapping

This document maps each Cosmos video to its target category in the `data/synthetic/` structure.

## Category Definitions

| Category | Risk Level | Description |
|----------|------------|-------------|
| `normal` | Low (0-25) | Expected activity, no threat |
| `suspicious` | Medium (26-60) | Unusual behavior, warrants attention |
| `threats` | High/Critical (61-100) | Active threat, immediate concern |

---

## Series Overview

| Series | Videos | Primary Category | Description |
|--------|--------|------------------|-------------|
| **C** | C01-C23 | `suspicious` | Core detection scenarios |
| **E** | E01-E22 | `normal` | Everyday expected activity |
| **F** | F01-F16 | `normal` | False alarm triggers |
| **P** | P01-P48 | mixed | Presentation demos |
| **R** | R01-R18 | `threats` | Risk/threat scenarios |
| **T** | T01-T40 | `threats` | Training threat data |

---

## E-Series: Everyday Activity → `normal`

| Video ID | Scenario | Description |
|----------|----------|-------------|
| E01 | amazon_delivery | Amazon driver delivers package |
| E02 | fedex_delivery | FedEx driver delivers package |
| E03 | ups_delivery | UPS driver delivers package |
| E04 | usps_delivery | USPS mail carrier delivery |
| E05 | doordash_delivery | DoorDash food delivery |
| E06 | instacart_delivery | Instacart grocery delivery |
| E07 | landscaper | Landscaping service worker |
| E08 | pool_cleaner | Pool cleaning service |
| E09 | pest_control | Pest control technician |
| E10 | mail_carrier | Regular mail delivery |
| E11 | newspaper_delivery | Newspaper delivery person |
| E12 | meter_reader | Utility meter reader |
| E13 | cable_tech | Cable/internet technician |
| E14 | window_washer | Window cleaning service |
| E15 | tree_trimmer | Tree trimming service |
| E16 | irrigation_tech | Irrigation system tech |
| E17 | roofer | Roofing contractor |
| E18 | real_estate | Real estate showing |
| E19 | house_sitter | House sitter arrival |
| E20 | babysitter | Babysitter arrival |
| E21 | pet_sitter | Pet sitter arrival |
| E22 | house_cleaner | House cleaner arrival |

---

## F-Series: False Alarms → `normal`

| Video ID | Scenario | Description |
|----------|----------|-------------|
| F01 | deer | Deer walking across yard |
| F02 | rabbit | Rabbit in yard |
| F03 | squirrel | Squirrel activity |
| F04 | raccoon | Raccoon at night |
| F05 | stray_cat | Stray cat on property |
| F06 | bird | Bird activity near camera |
| F07 | wind_debris | Wind blowing debris |
| F08 | rain_sprinkler | Rain or sprinkler activation |
| F09 | shadow_movement | Moving shadows |
| F10 | car_headlights | Passing car headlights |
| F11 | sun_glare | Sun glare on camera |
| F12 | cloud_shadow | Cloud shadow movement |
| F13 | child_toy | Child retrieving toy |
| F14 | dog_walker | Dog walker passing by |
| F15 | jogger | Jogger passing property |
| F16 | lost_neighbor | Neighbor looking for pet |

---

## C-Series: Core Detection → `suspicious`

| Video ID | Scenario | Description |
|----------|----------|-------------|
| C01 | night_rain_approach | Person approaches in rain at night |
| C02 | night_approach | Person approaches at night |
| C03 | dusk_approach | Person approaches at dusk |
| C04 | day_approach | Person approaches during day |
| C05 | night_loiter | Person loiters at night |
| C06 | dusk_loiter | Person loiters at dusk |
| C07 | backyard_night | Person in backyard at night |
| C08 | side_yard_night | Person in side yard at night |
| C09 | driveway_night | Person in driveway at night |
| C10 | garage_approach | Person approaches garage |
| C11 | fence_check | Person checking fence |
| C12 | window_look | Person looking in windows |
| C13 | door_check | Person checking door |
| C14 | multiple_visits | Multiple approach events |
| C15 | slow_approach | Slow cautious approach |
| C16 | fast_approach | Fast approach |
| C17 | phone_usage | Person using phone while loitering |
| C18 | looking_around | Person looking around property |
| C19 | waiting | Person waiting at property |
| C20 | pacing | Person pacing |
| C21 | hood_up | Person with hood up |
| C22 | dark_clothing | Person in dark clothing |
| C23 | backpack | Person with backpack |

---

## P-Series: Presentation → mixed

### P01-P12: Threat Escalation Demo

| Video ID | Category | Risk | Description |
|----------|----------|------|-------------|
| P01 | `normal` | low | Delivery baseline |
| P02 | `suspicious` | medium | Lingering at door |
| P03 | `suspicious` | high | Window peering |
| P04 | `suspicious` | high | Testing door handle |
| P05 | `suspicious` | high | Circling house |
| P06 | `suspicious` | high | Return visit |
| P07 | `threats` | critical | Crouching near entry |
| P08 | `threats` | critical | Carrying tool/pry bar |
| P09 | `threats` | critical | Forced entry attempt |
| P10 | `suspicious` | high | Hooded, face hidden |
| P11 | `threats` | critical | Multiple checks (door/window/garage) |
| P12 | `suspicious` | high | Flees when light activates |

### P13-P24: Cross-Camera Tracking Demo

| Video ID | Category | Risk | Description |
|----------|----------|------|-------------|
| P13 | `suspicious` | medium | Driveway to door |
| P14 | `suspicious` | medium | Door to side yard |
| P15 | `suspicious` | high | Full perimeter walk |
| P16 | `suspicious` | medium | Vehicle exit, approach |
| P17 | `suspicious` | high | Backyard entry |
| P18 | `suspicious` | high | Garage check |
| P19 | `suspicious` | high | Walking to running |
| P20 | `suspicious` | medium | Disappear/reappear |
| P21 | `threats` | critical | Two people split up |
| P22 | `suspicious` | medium | Loiter multiple zones |
| P23 | `suspicious` | medium | Quick traverse |
| P24 | `suspicious` | medium | Slow deliberate |

### P25-P36: Household Recognition Demo

| Video ID | Category | Risk | Description |
|----------|----------|------|-------------|
| P25 | `normal` | low | Known resident returns |
| P26 | `normal` | low | Resident with groceries |
| P27 | `normal` | low | Resident with dog |
| P28 | `normal` | low | Resident checking mail |
| P29 | `normal` | low | Two known residents |
| P30 | `normal` | low | Resident takes trash out |
| P31 | `normal` | low | Known car arrives |
| P32 | `normal` | low | Resident unusual time |
| P33 | `normal` | low | Resident unusual time (rushed) |
| P34 | `normal` | low | Visitor with resident |
| P35 | `normal` | low | Known child playing |
| P36 | `suspicious` | medium | Unknown child in yard |

### P37-P48: Vehicle + Person Demo

| Video ID | Category | Risk | Description |
|----------|----------|------|-------------|
| P37 | `suspicious` | medium | Sedan approach |
| P38 | `normal` | low | Delivery van |
| P39 | `suspicious` | medium | Unknown pickup truck |
| P40 | `suspicious` | medium | Two people exit vehicle |
| P41 | `suspicious` | medium | Front plate visible |
| P42 | `suspicious` | medium | Rear plate visible |
| P43 | `suspicious` | medium | Quick dropoff |
| P44 | `suspicious` | high | Idling vehicle, no exit |
| P45 | `suspicious` | medium | Reverse into driveway |
| P46 | `suspicious` | medium | Motorcycle arrival |
| P47 | `normal` | low | Cyclist approaches |
| P48 | `suspicious` | high | Vehicle at night |

---

## R-Series: Risk/Threats → `threats`

| Video ID | Scenario | Description |
|----------|----------|-------------|
| R01 | package_grab | Quick package grab and run |
| R02 | package_distraction | Distraction theft |
| R03 | follow_delivery | Following delivery driver |
| R04 | box_swap | Swapping package contents |
| R05 | porch_pirate | Classic porch piracy |
| R06 | vehicle_theft | Package theft from vehicle |
| R07 | window_check | Checking windows for entry |
| R08 | door_handle_test | Testing door handles |
| R09 | lock_picking | Attempting to pick lock |
| R10 | forced_entry | Forcing door open |
| R11 | window_break | Breaking window |
| R12 | garage_entry | Attempting garage entry |
| R13 | casing_photos | Taking photos of property |
| R14 | marking_property | Marking property |
| R15 | lookout | Acting as lookout |
| R16 | escape_route | Planning escape route |
| R17 | return_pattern | Suspicious return pattern |
| R18 | group_approach | Group approaching property |

---

## T-Series: Training Threats → `threats`

| Video ID | Scenario | Description |
|----------|----------|-------------|
| T01 | weapon_handgun | Person with visible handgun |
| T02 | weapon_knife | Person with visible knife |
| T03 | weapon_bat | Person with baseball bat |
| T04 | aggressive_stance | Aggressive body posture |
| T05 | kicking_door | Person kicking door |
| T06 | window_break | Breaking window |
| T07 | pry_bar_usage | Using pry bar on door |
| T08 | masked_intruder | Ski mask and gloves |
| T09 | multiple_intruders | Group of threatening individuals |
| T10 | vehicle_ramming | Aggressive vehicle approach |
| T11-T40 | tracking_variations | Various tracking/ReID scenarios |

---

## Summary Statistics

| Category | Video Count | Unique IDs |
|----------|-------------|------------|
| `normal` | 54 | E01-E22, F01-F16, P01, P25-P35, P38, P47 |
| `suspicious` | 75 | C01-C23, P02-P06, P10, P12-P20, P22-P24, P36-P37, P39-P46, P48 |
| `threats` | 78 | R01-R18, T01-T40, P07-P09, P11, P21 |
| **Total** | **207** | |

---

## Migration Notes

1. Only `*_5s.mp4` files should be migrated (10s/30s are duplicates)
2. Video ID determines the target directory name
3. Expected labels derived from prompt and manifest
4. Screenshots in `cosmos/screenshots/` can be used for validation reference
