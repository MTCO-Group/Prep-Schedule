import streamlit as st
import json
import base64
import re
import requests
import pandas as pd
from datetime import date, timedelta, datetime
import io
# Streamlit runs this file top to bottom on every rerun, so an import
# has to appear ABOVE the first line that runs and uses it, not just
# above the function that references it. This one used to sit further
# down next to _pill; the materials dialog is opened by module level
# code earlier than that, so opening a materials request raised
# NameError: _html_esc. Keep escaping imports up here.
import html as _html_esc
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Kensite Prep Schedule", layout="wide", page_icon="🏗️")

# ── Brand constants ───────────────────────────────────────────────────────────
K_GREEN      = "#0d823b"
K_GREEN_DARK = "#0a6630"
K_GREEN_PALE = "#e8f5ee"
K_GREY       = "#40424a"
K_LGREY      = "#dadada"
K_WHITE      = "#ffffff"

_SVG_RAW = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 40"><rect width="120" height="40" rx="4" fill="#0d823b"/><text x="10" y="27" font-family="Figtree,Calibri,sans-serif" font-weight="800" font-size="18" fill="white" letter-spacing="1">KENSITE</text></svg>'
_SVG_B64 = base64.b64encode(_SVG_RAW.encode()).decode()
KENSITE_LOGO_HTML = f'<img src="data:image/svg+xml;base64,{_SVG_B64}" height="32" alt="Kensite"/>'

UNIT_TYPES = [
    "32ft AV", "24ft AV", "20ft AV", "10ft AV",
    "Mobile Welfare", "Static Welfare",
    "20ft Store", "10ft Store",
    "Stairs", "2+1", "3+1", "4+2",
    "Tank", "Steps", "IBC", "Generator",
    "Solar Loo Single", "Solar Loo Double", "Chemiloo",
    "Smoking Shelter",
]

# AV units that support configuration breakdown
AV_UNITS = {"32ft AV", "24ft AV", "20ft AV", "10ft AV"}
AV_CONFIGS = ["Canteen", "Office", "Drying Room", "Changing Room", "Welfare", "Meeting Room", "Other"]

# Units counted as delivered/collected assets (excludes accessories)
ASSET_UNITS = {
    "32ft AV", "24ft AV", "20ft AV", "10ft AV",
    "Mobile Welfare", "Static Welfare",
    "20ft Store", "10ft Store",
    "Solar Loo Single", "Solar Loo Double", "Chemiloo",
    "Smoking Shelter", "Generator",
}

JOB_TYPES = ["On Hire", "Off Hire", "Site Move"]
TEAM_MEMBERS = ["Jake", "Ewa", "Klaudia", "Chris", "Nick", "Chloe", "Peter", "Claude", "Nathan"]
MATERIALS_NAMES = ["Alex", "Baz", "Carl", "Cliff", "Dan", "Jim", "Keaton", "Matt", "Mel", "Mitch", "Ste"]
# Who can mark a materials request as ordered
MATERIALS_ORDERERS = ["Mitch", "Pete", "Ken"]

# Materials request categories -> items (A-Z, every category ends with
# Other). "Vinyl Floor" under Joinery is floor covering; "Vinyls"
# under External is livery/graphics.
# Generated from Danfast Catalogue.json (synced 14/08/2026, 937
# products). Regenerate when the portal range changes.
DANFAST_TREE = {
    'Adhesives & Sealants': {
        'CT1 Sealant & Adhesive': [
            '*CT1 Grey Adhesive & Sealant 290ml',
            '*CT1 White Adhesive & Sealant 290ml',
        ],
        'Expanding Foam': [
            '750ml Soudafoam 1K Polyurethene Expanding Foam',
        ],
        'Flashband': [
            'Grey 100mm Flashband (4") 10mtr Roll',
            'Grey 150mm Flashband (6") 10mtr Roll',
            'Grey 225mm Flashband (9") 10mtr Roll',
            'Grey 300mm Flashband (12") 10mtr Roll',
        ],
        'General': [
            '*Fix All High Tack White 290ml Super Strong SMX Sealant',
            '*Seamseal CV Non Drying Bedding/Sealant White',
            '380ml Evode Gunnable Adhesive C30 Hard Cartridges',
            '400ml Silicone Spray',
            'Clear 500ml Evode Gp Spray Adhesive',
            'Grey 295ml Silirub A Silicone Low Modulus',
            'White 290ml Fix All Adhesive Sealant With Fungicide',
            'White 300ml Acryrub Int/Ext Acrylic Sealant',
        ],
        'Roofing Products': [
            'Restec Acryltex Storm Grey Roof Coating 5KG Tin P168001',
        ],
        'Silicone Sealant': [
            'Black 270ml Multi Purpose Silicone',
            'Brown 270ml Multi Purpose Silicone',
            'Clear 270ml Multi Purpose Silicone',
            'White 270ml Multi Purpose Silicone',
        ],
    },
    'Canteen & Furniture': {
        '1000 x 600 Roll Front Stainless Steel Sink': [
            '1000 x 600 Roll Front Left Hand Drainer St/Steel Sink',
            '1000 x 600 Roll Front Right Hand Drainer St/Steel Sink',
        ],
        '1000 x 600 Square Front Stainless Steel Sink': [
            '1000 x 600 Square Front LH Drainer St/Steel Sink',
            '1000 x 600 Square Front RH Drainer St/Steel Sink',
        ],
        'Appliances': [
            '2 Slice White Toaster',
            '48cm Under Counter Fridge',
            'Jug Kettle',
            'Microwave Oven White',
        ],
        'Bench': [
            'Thetford C402C Right Hand (OEM)',
        ],
        'Cabinets': [
            '1000 x 600 Drawerline Base Unit, Plastic Legs',
            'Double Wall Unit 1000 x 720',
        ],
        'Dometic 9222 Combi Unit': [
            'Dometic 9222R Combi Unit RH Sink, Piezo Ign, Gas Shut Off',
            'Dometic 9222S Combi Unit 2 Burner LH Sink',
        ],
        'Dometic 9722 Combi Unit': [
            'Dometic 9722 Slim-Line Combi Unit c/w Piezo Ignition RH Sink',
        ],
        'General': [
            '15mm x 3/4"BSP Appliance Valve DM Fit (Black)',
            'Hat And Coat Hook Aluminium',
            'Hat And Coat Hook SAA 4mm Thk Heavy Duty',
        ],
        'Hat & Coat Hooks': [
            '4 Chrome Hooks On Teak Effect Wooden Mount',
            '6 Hat And Coat Hooks Rail 708mm Long White Powder Coated',
        ],
        'LED - Mains': [
            '5ft LED Batten c/w Microwave Sensor IP20 Adjustable',
        ],
        'Noticeboards & Drywipe': [
            '1200 x 900 Blue Felt Combi Notice/Drywipe Boards',
            "3' x 2' Blue Noticeboard Aluminium Frame",
            "4' x 3' Blue Noticeboard Aluminium Frame",
            "4' x 3' Magnetic Drywipe Board c/w Fixing Kit & Pen Tray",
            "4' x 3' Reversible Notice Board / Magnetic Drywipe Board",
            '900 x 600 Blue Felt Combi Notice/Drywipe Boards',
        ],
        'Refrigeration': [
            'Dometic NRX 50C Fridge, 44L c/w Removable Freezer, 12/24v',
        ],
        'Sink Base Unit Kit': [
            '1.1/2" Combined Sink Waste',
            '1000 x 600 Gable Ended Base Unit 2 Door White',
        ],
        'Sink Plugs': [
            'Sink Plug 1.1/2"',
            'Sink Plug 1.3/4"',
        ],
    },
    'Doors & Security': {
        '12" Sweeping Brush': [
            'Soft Sweeping Brush 12" c/w Handle',
            'Stiff Sweeping Brush 12" c/w Handle',
        ],
        '24" Platform Broom': [
            'Platform Broom Soft 24" c/w Handle',
            'Platform Broom Stiff 24" c/w Handle',
        ],
        'Door Closers': [
            'Arrone Door Closer Size 2-4',
            'Arrone Door Closer Size 3 (Up To 60Kg Door)',
            'Door Closer White Sprung Arm Architrave Fix',
            'Union Door Closer Size 2 - 5 (100Kg Door)',
            'Union Door Closer Size 3 60kg Door',
            'Union Door Closer Up To 120Kg (Size 6)',
        ],
        'Door Furniture': [
            '3" No.104 Hurlinge BZP (Pair) Fixed Pin',
            'Door Stop Black 1.3/8"',
            'Finger / Push Plate SAA 300mm x 75mm',
            'Kick Plate SAA 760mm x 150mm',
        ],
        'Door Handles': [
            'Black Plastic Pull Handle 246mm',
            'Door Handle 19mm Bar Lever On Rose PAA (Pair)',
            'SAA 19mm Sprung Euro Lock Handle',
            'SAA 19mm Sprung Keyhole Lock Handle',
            'SAA Latch Handle',
            'SAA Lock Handle',
        ],
        'Door Signs': [
            'Female Sign SAA 150mm x 100mm',
            'Male Sign SAA 150mm x 100mm',
        ],
        'Era 3 Lever Sash Lock': [
            'Era 3 Lever 2.1/2" Sash Lock 473-61',
            'Era 3 Lever 3" Sash Lock 573-61',
        ],
        'Era 5 Lever Deadlock': [
            'Era 5 Lever 2.1/2" Deadlock 201-31',
            'Era 5 Lever 3" Deadlock 301-31',
        ],
        'Era 5 Lever Sash Lock': [
            'Era 5 Lever 2.1/2" Sash Lock 202-61',
            'Era 5 Lever 3" Sash Lock 302-61',
        ],
        'Era Fortress 5 Lever Deadlock': [
            'Era Fortress 2.1/2" 5 Lever Deadlock 261-31 - Key No.1',
            'Era Fortress 2.1/2" 5 Lever Deadlock 261-31 - Key No.2',
            'Era Fortress 2.1/2" 5 Lever Deadlock 261-31 - Key No.3',
            'Era Fortress 2.1/2" 5 Lever Deadlock 261-31 - Key No.4',
            'Era Fortress 2.1/2" 5 Lever Deadlock 261-31 - Key No.5',
            'Era Fortress 2.1/2" Deadlock 5 Lever 261-31',
            'Era Fortress 3" Deadlock 5 Lever 361-31',
        ],
        'Era Fortress 5 Lever Sash Lock': [
            'Era Fortress 2.1/2" Sash Lock 5 Lever 262-31',
            'Era Fortress 3" Sash Lock 5 Lever 362-31',
        ],
        'General': [
            'Auxiliary Lock To Suit Steel Security Door',
            'Door Holder Male Part Only',
            'Flush Bolt To Suit Steel Security Window Shutter',
            'Hooply Lever Door Handles LH Hinged Door (Pair) 2018T',
            'Hooply Lever Door Handles RH Hinged Door (Pair) 2018T',
            'Hooply Mortice Lock',
            'Modesty Screw Block White',
            'Recessed Handle To Suit Steel Security Window Shutter',
            'Scavenger Brush 13" c/w Handle',
            'Soft Black Rubber Door Retainer Female',
            'Stainless Hinge To Suit Steel Security Door (Single)',
            'Stainless Left Hand Hinge For Steel Security Window Shutter',
            'Stainless Right Hand Hinge For Steel Security Window Shutter',
            'Wooden Mop Handle 48"',
        ],
        'Locks & Latches': [
            '2.1/2" Union C Series 5 Lever Mortice Lock B-3G115',
            '64mm Mortice Latch Face Plate Nickel Plated',
            'Arrone Keysafe Unit',
            'Arrone Mechanical Push Button Door Lock',
            'Euro Profile Single Cylinder NP',
        ],
        'Paint Brushes & Rollers': [
            '9" Soft Grip Roller Prolock Frame',
        ],
        'Security Door Accessories': [
            '6Mtr Black Frame Seal for Steel Doors',
            'Anti-Snap Thumbturn Cylinder T40/40N with 6 keys',
            'Hooply Stainless Lever Door Handles for LH Hinged Door',
            'Hooply Stainless Lever Door Handles for RH Hinged Door',
        ],
        'Steel Butt Hinge': [
            'Butt Hinge Steel 3" (Pairs) 1838',
            'Butt Hinge Steel 4" (Pairs) 1838',
        ],
        'Union 2 Lever Sash Lock': [
            'Union Sash Lock 2.1/2" 2-Lever 2-Keyed J2295',
            'Union Sash Lock 3" 2-Lever 2-Keyed J2295',
        ],
        'Union 3 Lever Sash Lock': [
            'Union Sash Lock 2.1/2" 3-Lever J2277',
            'Union Sash Lock 3" 3-Lever J2277',
        ],
        'Union 5 Lever Deadbolt': [
            'Union Deadlock 2.1/2" 5-Lever J2101',
            'Union Deadlock 3" 5-Lever J2101',
        ],
        'Union 5 Lever Sash Lock': [
            'Union Sash Lock 3" 5-Lever J2201',
        ],
        'Union Mortice Latch': [
            'Union Mortice Latch 2.1/2" J2642',
            'Union Mortice Latch 3" J2642',
        ],
    },
    'Electrical': {
        '1.5mm Single Cable 6491X': [
            '1.5mm Cable Blue 100M Coil',
            '1.5mm Cable Brown 100M Coil',
            '1.5mm Cable Green & Yellow 100M Coil',
        ],
        '13amp Plugs': [
            '13A White Heavy Duty Plug Thermoplastic',
            '13A White Plastic Plug',
        ],
        '2.5mm Single Cable 6491X': [
            '2.5mm Cable Blue 100M Coil',
            '2.5mm Cable Brown 100M Coil',
            '2.5mm Cable Green & Yellow 100M Coil',
        ],
        '240v Plug IP44': [
            'Gewiss GW60004H 16A 2P+E 240v Plug IP44',
            'Gewiss GW60015H 32A 2P+E 240V Plug IP44',
        ],
        '240v Plug IP67': [
            'Gewiss GW60026H 16a 2P+E 240v Plug IP67',
            'Gewiss GW60037H 32A 2P+E 240V Plug IP67',
        ],
        '240v Plugs & Sockets': [
            'Gewiss GW60437 32A 2P+E 240v Wall Mounted Plug IP67',
            'Gewiss GW61448 63a 230v 2P&E Wall Mount Inlet IP67',
            'Gewiss GW62488 32A 2P+E 240V Wall Mounted Socket IP44',
        ],
        '240v Socket Outlet IP44': [
            'Gewiss GW62004H 16A 2P+E 240v IP44 Connector',
            'Gewiss GW62015H 32A 2P+E 240v Connector IP44',
        ],
        '240v Socket Outlet IP67': [
            'Gewiss GW62026H 16a 2P+E 240v Socket Outlet IP67',
            'Gewiss GW62037H 32A 2P+E 240v Socket Outlet IP67',
        ],
        '240v Wall Mounted Plug IP44': [
            'Gewiss GW60404 16A 2P+E 240V Wall Mounted Plug IP44',
            'Gewiss GW60415 32A 2P+E 240v Wall Mounted Plug IP44',
        ],
        '3 Core Flex 3183Y': [
            '1.5mm 3 Core Flex White 50M Coil',
            '2.5mm Arctic Blue 3 Core Flex 100M Coil',
            '2.5mm White 3 Core Flex 50M Coil',
        ],
        'Blank Plate': [
            '1 Gang Blank Plate',
            '2 Gang Blank Plate',
        ],
        'Cable': [
            '1.5mm Grey Flat 3 Core & Earth Cable 100M 6243Y',
            '10.0mm 3 Core PVC SWA Cable 10Mtr Coil 6493X',
        ],
        'Cable Grommet': [
            '20mm Cable Grommet Blind',
            '20mm Cable Grommet Open',
            '25mm Cable Grommet Closed',
        ],
        'Cartridge Fuse Niglon': [
            '13A Cartridge Fuse Niglon',
            '3A Cartridge Fuse Niglon',
            '5A Cartridge Fuse Niglon',
        ],
        'Conduit & Fittings': [
            '20mm Conduit Coupler White',
            '20mm Conduit Female Adaptor White',
            '20mm Conduit Inspection Bend White',
            '20mm Conduit Male Adaptor White',
            '20mm Conduit Spring Saddle Clips White',
            '20mm White Conduit Pvc 3Mtr',
        ],
        'Consumer Unit Spares': [
            'Blanking Plate 3 Module',
            'Hager JK01B MCB Blanks',
            'Hager VAB08 8-Module Busbar (Insulated)',
        ],
        'Consumer Units': [
            'Cudis RO232C/030 32A Dp Type C 30Ma RCBO',
            'Hager CDA263U 63A Dp 30Ma RCD',
        ],
        'Control Switches': [
            'CED Surface Mounting Switch TP&N 63A (Narrow Type) IP66',
            'Rotary Control Switch Red 63A, 4 Pole, IP65',
            'Timeguard Isolator Switch 63A 4 Pole IP66',
        ],
        'Controllers': [
            'SLPBG Wireless Controller c/w Thermostat & Generator Program',
            'SLVTG Wireless Control c/w Generator Program',
        ],
        'Dado Trunking': [
            'Marco MT105 100 X 50mm Dado Trunking 3mtr',
            'Marco MTC105 Dado Trunking Stop End',
            'Marco MTSB1 1 Gang Back Box for Dado Trunking',
            'Marco MTSB2 2 Gang Back Box for Dado Trunking',
        ],
        'Deligo Quick Connector Terminals': [
            'Deligo 2 Pole Quick Connector Terminal Pack of 50',
            'Deligo 3 Pole Quick Connector Terminal Pack of 50',
        ],
        'Dry Line Box': [
            '1 Gang Dry Line Box',
            '2 Gang Dry Line Box',
        ],
        'Garage Consumer Unit': [
            'Live 4 Module Metal Bodied Garage Consumer Unit 63A RCD',
        ],
        'General': [
            '15mm Straight Connector DM Fit',
            '15mm x 10mm Straight Connector DM Fit',
            '22mm Straight Connector DM Fit',
            '22mm x 15mm Straight Connector DM Fit',
            '25mm Chrome Round Socket',
            'Aluminium Extension Pole Long Reach',
            'Pull Cord Ceiling Switch 10A',
            'Pull Cord Ceiling Switch With Neon 45Amp',
            'SA62 White 110mm Screwed Access Plug',
            'Socket Mop Head 12PY',
            'White 300ml Paint Flex Filler Decorators Caulk',
        ],
        'Hager MTN MCB': [
            'Hager MTN106 6A Sp MCB',
            'Hager MTN110 10A Sp MCB',
            'Hager MTN116 16A Sp MCB',
            'Hager MTN120 20A Sp MCB',
            'Hager MTN132 32A Sp MCB',
            'Hager MTN140 40A Sp MCB',
        ],
        'Hager Metal Bodied Consumer Unit c/w 63A RCD': [
            'Hager VME406AH 6-Module Metal Consumer Unit c/w 63A RCD',
            'Hager VME410AH 10-Module Metal Consumer Unit c/w 63A RCD',
        ],
        'Misc Essentials': [
            '20mm Compression Gland And Nut White',
            '370 x 4.8 Natural Cable Ties',
            'White 1 Hole 2.5mm P Type Cable Clip',
        ],
        'Pattress': [
            '1 Gang Pattress 25mm Deep',
            '1 Gang Pattress 32mm Deep',
            '1 Gang Pattress 47mm Deep',
            '2 Gang Pattress 25mm Deep',
            '2 Gang Pattress 35mm Deep',
        ],
        'Plate Switch': [
            '1 Gang 1 Way Plate Switch',
            '1 Gang 2 Way Plate Switch',
            '2 Gang 2 Way Plate Switch',
            '3 Gang 2 Way Plate Switch',
        ],
        'Pozi Bits & Blades': [
            '5/16 Mag Socket & Drive Bar To Suit Hex Head Screws',
        ],
        'Round Cable Clips White': [
            '10-14mm Round Cable Clip White',
            '7-10mm Round Cable Clip White',
        ],
        'Schneider Acti9 MCB': [
            'Schneider 16A MCB C60HB 1P B BSEN Acti9',
            'Schneider 20A MCB C60HB 1P B BSEN Acti9',
        ],
        'Socket Plug': [
            'SP296 Grey 110mm Socket Plug',
            'SP296 White 110mm Socket Plug',
            'WP30 White 32mm Socket Plug',
            'WP31 White 40mm Socket Plug',
        ],
        'Soil Double Socket': [
            'SP105 Grey 110mm Double Socket Straight Coupling',
            'SP105 White 110mm Double Socket Straight Coupling',
        ],
        'Soil Offset Bend 135°': [
            'SP435 White 110mm Offset Bend Single Socket 135 Degree',
            'SP440 White 110mm Offset Bend Double Socket 135 Degree',
        ],
        'Soil Single Socket': [
            'SP124 White 110mm Single Socket',
        ],
        'Soil Socket Bend 92.5°': [
            'SP161 Grey 110mm Single Socket Bend 92.5 Degree',
            'SP161 White 110mm Single Socket Bend 92.5 Degree',
            'SP561 Black 110mm Bend Double Socket 92.5 Degree',
            'SP561 White 110mm Bend Double Socket 92.5 Degree',
        ],
        'Soudaflex 40FC Adhesive/Sealant': [
            'Black 310ml Soudaflex 40FC',
            'Grey 310ml Soudaflex 40FC',
            'White 310ml Soudaflex 40FC',
        ],
        'Strip Connector': [
            '15A Strip Connector',
            '30A Strip Connector',
            '5A Strip Connector',
        ],
        'Switched Fused Spurs': [
            'Switched Fused Spurs',
            'Switched Fused Spurs c/w Neon',
        ],
        'Switched Socket': [
            '1 Gang Switched Socket',
            '2 Gang Switched Socket',
            '2 Gang Switched Socket c/w Dual USB Charger Type A & C',
        ],
        'Switches & Sockets': [
            '20A Dp Switch',
        ],
        'Trunking': [
            '25mm x 16mm Mini Trunking 3Mtr Self Adhesive',
            '38mm x 25mm Mini Trunking 3Mtr Self Adhesive',
        ],
        'Trunking Fittings': [
            '25mm x 16mm Adaptor To Suit Trunking',
            '25mm x 16mm External Corner For Mini Trunking',
            '25mm x 16mm Internal Corner For Mini Trunking',
            '25mm x 16mm L Shaped Flat Corner For Mini Trunking',
            '25mm x 16mm Tee For Mini Trunking',
            '38mm Tee For Mini Trunking',
            '38mm x 25mm Internal Corner For Mini Trunking',
            '38mm x 25mm L Shaped Flat Corner For Mini Trunking',
        ],
        'Trunking Pattress': [
            '1 Gang 32mm Pattress To Suit Trunking',
            '2 Gang 25mm Pattress To Suit Trunking',
            '2 Gang 32mm Pattress To Suit Trunking',
        ],
        'Twin & Earth Cable 6242Y': [
            '1.0mm T & E Grey 100M Coil',
            '1.5mm T & E Grey 100M Coil',
            '2.5mm T & E Grey 100M Coil',
            '6.0mm T & E Grey 50M Coil',
        ],
    },
    'Fastenings & Fixings': {
        '25mm x 14g Plastic Head Pins': [
            '25mm x 14G Dk Brown Plastic Headed Pins Zinc Plated',
            '25mm x 14G White Plastic Headed Pins Zinc Plated',
        ],
        '30mm x 14g Plastic Head Pins': [
            '30mm x 14G Dk Brown Plastic Headed Pins Zinc Plated',
            '30mm x 14G White Plastic Headed Pins Zinc Plated',
        ],
        '40mm x 10g Plastic Head Nails': [
            '40mm x 10G White Plastic Headed Nails Large Head Zinc Plated',
        ],
        '40mm x 14g Plastic Head Pins': [
            '40mm x 14G White Plastic Headed Pins Zinc Plated',
        ],
        'Black Drywall Screws': [
            '3.5mm x 25 Bugle Hd Drywall Screw Black',
            '3.5mm x 32 Bugle Hd Drywall Screw Black',
            '3.5mm x 35 Bugle Hd Drywall Screw Black',
            '3.5mm x 38 Bugle Hd Drywall Screw Black',
            '3.5mm x 42 Bugle Hd Drywall Screw Black',
            '3.5mm x 50 Bugle Hd Drywall Screw Black',
            '4.2mm x 65 Bugle Hd Drywall Screw Black',
            '4.2mm x 75 Bugle Hd Drywall Screw Black',
        ],
        'Bugle Head Self Drilling Screw': [
            '3.5 x 50 Bugle Head Self Drill Screw',
            '4.2 x 65 Bugle Head Self Drill Screw',
        ],
        'Csk Pozi Chipboard Screws Yellow': [
            '3.5 x 16 Csk Pozi Chipboard Screw Z&Y',
            '3.5 x 20 Csk Pozi Chipboard Screw Z&Y',
            '3.5 x 25 Csk Pozi Chipboard Screw Z&Y',
            '3.5 x 50 Csk Pozi Chipboard Screw Z&Y',
            '4 x 20 Csk Pozi Chipboard Screw Z&Y',
            '4 x 25 Csk Pozi Chipboard Screw Z&Y',
            '4 x 30 Csk Pozi Chipboard Screw Z&Y',
            '4 x 35 Csk Pozi Chipboard Screw Z&Y',
            '4 x 40 Csk Pozi Chipboard Screw Z&Y',
            '4 x 50 Csk Pozi Chipboard Screw Z&Y',
            '4 x 60 Csk Pozi Chipboard Screw Z&Y',
            '4 x 70 Csk Pozi Chipboard Screw Z&Y',
            '4.5 x 25 Csk Pozi Chipboard Screw Z&Y',
            '4.5 x 75 Csk Pozi Chipboard Screw Z&Y',
            '5 x 100 Csk Pozi Chipboard Screw Z&Y',
            '5 x 40 Csk Pozi Chipboard Screw Z&Y',
            '5 x 50 Csk Pozi Chipboard Screw Z&Y',
            '5 x 60 Csk Pozi Chipboard Screw Z&Y',
            '5 x 70 Csk Pozi Chipboard Screw Z&Y',
            '5 x 80 Csk Pozi Chipboard Screw Z&Y',
        ],
        'Csk Pozi Woodscrews BZP': [
            '10 x 1" Csk Pozi Woodscrews BZP',
            '10 x 1.1/2" Csk Pozi Woodscrews BZP',
            '10 x 2" Csk Pozi Woodscrews BZP',
            '10 x 2.1/2" Csk Pozi Woodscrews BZP',
            '10 x 3" Csk Pozi Woodscrews BZP',
            '10 x 4" Csk Pozi Woodscrews BZP',
            '6 x 1" Csk Pozi Woodscrews BZP',
            '6 x 1.1/2" Csk Pozi Woodscrews BZP',
            '6 x 1.1/4" Csk Pozi Woodscrews BZP',
            '6 x 3/4" Csk Pozi Woodscrews BZP',
            '7 x 1" Csk Pozi Woodscrews BZP',
            '8 x 1" Csk Pozi Woodscrews BZP',
            '8 x 1.1/2" Csk Pozi Woodscrews BZP',
            '8 x 1.1/4" Csk Pozi Woodscrews BZP',
            '8 x 1.3/4" Csk Pozi Woodscrews BZP',
            '8 x 1/2" Csk Pozi Woodscrews BZP',
            '8 x 2" Csk Pozi Woodscrews BZP',
            '8 x 2.1/2" Csk Pozi Woodscrews BZP',
            '8 x 3" Csk Pozi Woodscrews BZP',
            '8 x 3/4" Csk Pozi Woodscrews BZP',
        ],
        'Csk Self Drilling Screw': [
            '4.8 x 32 Csk Self Drill Screw',
            '4.8 x 50 Csk Self Drill Screw',
            '5.5 x 40 Csk Self Drilling Screw',
        ],
        'Csk Winged Self Drilling Screw': [
            '5.5 x 40 Csk Wing Drillscrew (Timber To Steel)',
            '5.5 x 60 Csk Wing Drillscrew (Timber To Steel)',
            '5.5 x 80 Csk Wing Drillscrew (Timber To Steel)',
        ],
        'Flat Washers Zinc Plated': [
            'M10 Form B Washers BZP',
            'M12 Form B Washers BZP',
            'M6 Form B Washers BZP',
            'M8 Form B Washers BZP',
        ],
        'General': [
            '1.1/4" - 3/4" Straight Caravan Waste S/S Top / Rubber Washer',
            '48mm Dia x 1.5mm Thick Galv Steel Washer With 5mm Hole',
        ],
        'HT Setscrews BZP': [
            'M10 x 100 HT Setscrews BZP',
            'M10 x 30 HT Setscrews BZP',
            'M10 x 40 HT Setscrews BZP',
            'M10 x 50 HT Setscrews BZP',
            'M10 x 75 HT Setscrews BZP',
            'M12 x 100 HT Setscrews BZP',
            'M12 x 120 HT Setscrews BZP',
            'M12 x 30 HT Setscrews BZP',
            'M12 x 40 HT Setscrews BZP',
            'M12 x 50 HT Setscrews BZP',
            'M12 x 60 HT Setscrews BZP',
            'M12 x 75 HT Setscrews BZP',
            'M12 x 80 HT Setscrews BZP',
            'M6 x 30 HT Setscrews BZP',
            'M6 x 50 HT Setscrews BZP',
            'M6 x 70 HT Setscrews BZP',
            'M8 x 50 HT Setscrews BZP',
        ],
        'Hex Full Nuts Zinc Plated': [
            'M10 Hex Full Nuts C/F BZP',
            'M12 Hex Full Nuts C/F BZP',
            'M6 Hex Full Nuts C/F BZP',
            'M8 Hex Full Nuts C/F BZP',
        ],
        'Hex Hd Self Drilling Screws': [
            '4.8 x 16mm Ind Hex Washer Hd BZP S/Drill Screw',
            '5.5 x 25 Hex Hd Self Drill Screw c/w Washer',
            '5.5 x 38 Hex Hd Self Drill Screw c/w Washer',
            '5.5 x 50 Hex Hd Self Drill Screw c/w Washer',
        ],
        'Jerrycans': [
            '25Ltr Natural Jerrycan With 61mm Screw Cap',
        ],
        'Repair Washers Zinc Plated': [
            'M10 x 40 x 1.5 Repair Washers BZP',
            'M12 x 38 x 1.5 Repair Washers BZP',
        ],
        'Self Drilling Screws': [
            '4.2 x 16 Phillips Flange Head Self Drill Screw BZP',
            '4.8 x 19 Pan Head Self Drill Screw',
            'Plasterboard Self Drilling Anchor Metal',
        ],
        'Zinc Drywall Screws': [
            '3.5mm x 32 Bugle Hd Drywall Screw Z&Y',
            '3.5mm x 38 Bugle Hd Drywall Screw Z&Y',
        ],
    },
    'Fire Safety': {
        'Fire Clips': [
            '30mm Fire Safe Metal Clips (Base Measurement 23mm)',
            '40mm Fire Safe Metal Clips (Base Measurement 31mm)',
        ],
        'Fire Safety': [
            'Aico Heat Detector Alarm Mains With Battery EI144E',
        ],
        'Firecryl FR Sealant': [
            'Soudal Firecryl FR Sealant White 310ml',
        ],
        'Misc Gas': [
            'Arctic PH Gas Leak Detector Spray 400ml',
        ],
        'Smoke/CO Alarms': [
            'Aico EI208 Battery Carbon Monoxide Alarm',
            'Combined Smoke/Carbon Monoxide Alarm',
            'Kidde 5CO Carbon Monoxide Alarm',
            'Optical Smoke Alarm',
            'Smoke Detector 9v Battery',
        ],
    },
    'Flooring': {
        'General': [
            'Tremco SF105 Vinyl Adhesive 15Kg',
        ],
        'PVC Cova-Quick Rolls': [
            'Pvc Cova-Quick Roll 20Mtr x 210Cm',
            'Pvc Cova-Quick Roll 33Mtr x 110Cm',
            'Pvc Cova-Quick Roll 33Mtr x 55Cm',
        ],
        'Vinyl Flooring': [
            '*Slate Grey 1.5mm Thick x 2mtr wide x 27.5mtr Polyflor Standard XL Vinyl',
            'Black Panther 2mm thick x 2mtr wide x 20mtr Polyflor Standard XL Vinyl',
            'Graphite 1.5mm thick x 2mtr wide x 27.5mtr Polyflor Standard XL Vinyl',
            'Graphite 2mm thick x 2mtr wide x 20mtr Polyflor Standard XL Vinyl',
            'Mushroom 2mm thick x 2mtr wide x 20mtr Polyflor Standard XL Vinyl',
            'Slate Grey 2mm thick x 2mtr wide x 20mtr Polyflor Standard XL Vinyl',
        ],
        'Vinyl Weld Rod': [
            'Black Panther weld rod to suit Polyflor vinyl 100mtr coil',
            'Graphite weld rod to suit Polyflor vinyl 100mtr coil',
            'Mushroom weld rod to suit Polyflor vinyl 100mtr coil',
            'Slate Grey weld rod to suit Polyflor vinyl 100mtr coil',
        ],
    },
    'General & Misc': {
        'General': [
            '15mm Equal Elbow DM Fit',
            '15mm Equal Tee DM Fit',
            '15mm Stem Elbow DM Fit',
            '15mm x 1/2" BSP Male Coupler DMfit',
            '15mm x 1/2" BSPT Brass Male Coupler Polyplumb',
            '15mm x 1/2"BSP Male Coupler DM Fit',
            '22mm Equal Elbow DM Fit',
            '22mm Equal Tee DM Fit',
            '22mm x 1" Straight Male Compression',
            '22mm x 15mm Stem Reducer DM Fit',
            '22mm x 22mm x 15mm Reducing Tee DM Fit',
            '400ml Trade Skeleton Gun',
            'Carpet Strip 2" x 2440mm Aluminium Pack Of 10',
            'Double Euro Cylinder 40/40 Thumbturn Satin Finish',
            'Mcalpine Bath Waste FBW2PC',
            'Plastic Builders Bucket 10Ltr',
            'Plastic Mop Bucket Blue 12Ltr c/w Wringer',
            'Plastidome Cover Caps White',
            'Pot Magnet 50mm Dia x 10mm Thk With 5mm Centre Hole 18kg Pull',
            'Pozi Tops White',
            'Room Thermostat 10A',
            'Shrinking Bracket 2 Way Zinc Plated',
            'Small Plastic Key Fob',
            'Stockinette 2.4Kg Bag Length 6/7 All Cotton',
            'Swipex Heavy Duty Wipes (100 Per Cannister)',
            'TW471 Washing Machine Kit 76mm Seal',
            'Tamper Resistant Room Thermostat',
            'Timeguard 360 Degree Ceiling PIR',
            'Twine Polypropylene Spools 450Mtr/Kg',
            'White 110mm Reducer Waste Concentric - Requires Reducer',
            'White Cotton Rags 10Kg',
            'White Disposable Coverall Extra Large',
            'Zona Surface PIR Movement Sensor',
        ],
        'Swivel Bend': [
            'WP26 White 32mm Swivel Bend',
            'WP27 White 40mm Swivel Bend',
        ],
    },
    'Guttering & Roofline': {
        'Downpipe Shoe': [
            'RBS3 Black 65mm Downpipe Shoe',
            'RBS3 White 65mm Downpipe Shoe',
        ],
        'Gutter Union Bracket': [
            'RUS1 White Gutter Union Bracket',
        ],
        'Square Downpipe': [
            'RPS2.5 Black 65mm x 2.5Mtr Square Downpipe',
            'RPS2.5 White 65mm x 2.5Mtr Square Downpipe',
        ],
        'Stand-Off Downpipe Bracket': [
            'RCS1 Black 65mm Square Standoff Pipe Bracket',
            'RCS1 White 65mm Square Standoff Pipe Bracket',
        ],
    },
    'Lighting': {
        '2D External Bulkhead Light Square Base': [
            '14w LED Square Bulkhead Light Int/Ext Black IP65',
            '7w LED Square Bulkhead Light Int/Ext Black IP65',
        ],
        '50mm Bevelled Skirting SK022': [
            '50mm Bevelled Skirting Grey 3.00 Mtr SK022',
            '50mm Bevelled Skirting White 3.00 Mtr SK022',
        ],
        'Bulkhead Lights': [
            'LED 12/18W Square Bulkhead Light',
            'LED Bulb 8.5w GLS Bayonet Cap B22',
            'LED Emergency Bulkhead Light IP65 3w',
        ],
        'CLEARANCE LED/12v Lights': [
            '**** CLEARANCE **** Pierre 45mm Chrome LED Downlight Spring Mount',
            '**** CLEARANCE **** Rotatable LED Strip Light Grey Switched',
            '***** CLEARANCE ***** 120mm Surface Mount Switched Overhead LED Light',
            '***** CLEARANCE ***** Small LED Recessed Light Downlight',
        ],
        'Copper Tube': [
            '10mm x 1mm Wall Seamless Copper Tube 30Mtr Coils',
            '8mm x 0.8mm Wall PVC Coated Copper Tube 25mtr Coil',
            '8mm x 0.8mm Wall Seamless Copper Tube 30Mtr Coils',
        ],
        'Corners for 50mm Bevelled Skirting': [
            'External Corner For 50mm Bevelled Skirting White ZSK499',
            'Internal Corner For 50mm Bevelled Skirting White ZSK199',
        ],
        'Door Signs': [
            'Disabled Sign SAA 150mm x100mm',
        ],
        'General': [
            '1.1/4" - 3/4" Angled Caravan Waste c/w Plug',
            '15mm Tube Stop End DM Fit',
            '25mm Chrome x 2.5Mtr Round Tube',
        ],
        'LED - Mains': [
            '5ft LED Batten ML BATMCW5 CCT 22 - 41w',
            '5ft LED Bulkhead Light Fitting 45w 230v IP20',
            '5ft Single LED Light Fitting 28w-50w Non Corrosive IP65',
            'LED Starter To Suit T8 LED Tubes',
            'Reeve IP65 45W Daylight 5ft LED Fitting',
        ],
        'LED T8 Glass Tube': [
            '4ft 16W LED T8 Glass Tube 4000k',
            '5ft 22W LED T8 Glass Tube 4000k',
        ],
        'Single LED Ready T8 Batten': [
            '4ft Single LED Ready Batten Fitting T8',
            '5ft Single LED Ready Batten Fitting T8',
        ],
        'Switches & Sockets': [
            '1 Gang 10A Dp Emergency Test Key Switch',
        ],
    },
    'Painting & Decorating': {
        '4" Mini Roller Frames': [
            '11" Mini Roller Frame',
            '16" Mini Roller Frame',
            '21" Mini Roller Frame',
        ],
        '4" Mini Rollers': [
            '4" Silver Stripe Mini Roller (Pack Of 10)',
            '4" Simulated Mohair Roller Refill (Pack Of 10)',
            '4" Superfine Foam Roller Refill (Pack Of 10)',
        ],
        '9" Rollers': [
            '9" x 1.75 Green Elite Roller Refill 18mm Pile',
            '9" x 1.75" Roller Refill 11mm Pile',
            '9"x1.75" Ecofibre Tigerstripe Roller Refill 12mm Pile',
        ],
        'All Rounder Paint Brushes': [
            '1" All Rounder Mixed Bristle Brush',
            '1.1/2" All Rounder Mixed Bristle Brush',
            '1/2" All Rounder Mixed Bristle Brush',
            '2" All Rounder Paint Brush',
        ],
        'Bannister Hand Brush': [
            'Soft Bannister Brush',
            'Stiff Bannister Brush',
        ],
        'General': [
            'Scrubbing Brush PVC Shaped',
        ],
        'Paint Scuttles': [
            '12ltr Plastic Paint Scuttle',
            '15 Ltr Plastic Paint Scuttle',
            '8ltr Plastic Paint Scuttle',
        ],
        'Paint Trays': [
            '11" Plastic Roller Tray',
            'Paint Tray to suit 4" Roller',
            'Paint Tray to suit 9" Roller',
        ],
        'Painting Sundries': [
            '3" Soft Grip Paint Scraper',
        ],
    },
    'Plastics & Profiles': {
        '13.5mm J-Section JT013': [
            '13.5mm J-Section Cream 2.44 Mtr JT013',
            '13.5mm J-Section White 2.44 Mtr JT013',
            '13.5mm J-Section White 3.00 Mtr JT013',
        ],
        '13mm One Part H-Section HS033': [
            '13mm One Part H-Section White 2.44 Mtr HS033',
            '13mm One Part H-Section White 3.05 Mtr HS033',
        ],
        '15mm J-Section JT015': [
            '15mm J-Section White 2.44 Mtr JT015',
            '15mm J-Section White 3.00 Mtr JT015',
        ],
        '25 x 25 Angle AN010': [
            '25 x 25 Angle White 2.44 Mtr AN010',
            '25 x 25 Angle White 3.00 Mtr AN010',
        ],
        '25 x 25 Int Ribbed Angle TM035': [
            '25 x 25 Int Ribbed Angle Grey 3.00 Mtr TM035',
            '25 x 25 Int Ribbed Angle White 2.44 Mtr TM035',
            '25 x 25 Int Ribbed Angle White 3.00 Mtr TM035',
        ],
        '25 x 3 H-Section Base HS072': [
            '25 x 3 H-Section Base Mix 2.44 Mtr HS072',
            '25 x 3 H-Section Base Mix 3.05 Mtr HS072',
        ],
        '27mm D-Mould DM028/DM029': [
            '27mm D-Mould Base White 4.00 Mtr DM028',
            '27mm D-Mould Lid White 4.00 Mtr DM029',
        ],
        '32 x 32 Angle AN025': [
            '32 x 32 Angle White 2.44 Mtr AN025',
            '32 x 32 Angle White 3.00 Mtr AN025',
        ],
        '32mm D-Mould DM033/DM034': [
            '32mm D-Mould Base White 2.44 Mtr DM033',
            '32mm D-Mould Lid White 2.44 Mtr DM034',
        ],
        '38 x 38 Angle AN035': [
            '38 x 38 Angle White 2.44 Mtr AN035',
            '38 x 38 Angle White 3.00 Mtr AN035',
        ],
        '40 x 12.5 H-Section Base HS014': [
            '40 x 12.5 H Section Base Mix 3.66 Mtr HS014',
            '40 x 12.5 H-Section Base Mix 2.44 Mtr HS014',
            '40 x 12.5 H-Section Base Mix 3.05 Mtr HS014',
        ],
        '40 x 12.5 H-Section Lid HS068': [
            '40 x 12.5 H Section Lid White 3.66 Mtr HS018',
            '40 x 12.5 H-Section Lid White 2.44 Mtr HS018',
            '40 x 12.5 H-Section Lid White 3.05 Mtr HS018',
        ],
        '40 x 17 H-Section Base HS034': [
            '40 x 17 H-Section Base Mix 3.05Mtr HS034',
        ],
        '40 x 5 H-Section Lid HS039': [
            '40 x 5 H-Section Lid White 2.44 Mtr HS039',
            '40 x 5 H-Section Lid White 3.05 Mtr HS039',
        ],
        '40 x 9 H-Section Lid HS069': [
            '40 x 9 H-Section Lid White 2.44 Mtr HS069',
            '40 x 9 H-Section Lid White 3.05 Mtr HS069',
        ],
        '5/6mm J-Section JT016': [
            '5/6mm J-Section White 2.44 Mtr JT016',
        ],
        '50 x 50 Angle AN052': [
            '50 x 50 Angle White 2.44 Mtr AN052',
            '50 x 50 Angle White 3.00 Mtr AN052',
        ],
        '5mm One Part H-Section HS005': [
            '5mm One Part H-Section White 2.44 Mtr HS005',
            '5mm One Part H-Section White 3.05 Mtr HS005',
        ],
        '60mm Window Liner WL060': [
            '60mm Window Liner White 3.00 Mtr WL060',
        ],
        '75mm Skirting/Architrave SK034/SK035': [
            '75mm Skirting / Architrave Base Grey 3.00 Mtr SK034',
            '75mm Skirting / Architrave Lid Grey 3.00 Mtr SK035',
        ],
        '85mm Window Liner WL085': [
            '85mm Window Liner White 3.00 Mtr WL085',
        ],
        'Corners for Architrave ZST034': [
            'Corner Cap For 34mm Architrave White ZST034',
        ],
        'Flat Architrave for Window Liner ST034': [
            '34mm Architrave To Suit Window Liner White 3.00 Mtr ST034',
        ],
        'General': [
            'Angle Bracket 19mm x 19mm Zinc Plated',
            'Trimming Knife Blade Heavy Duty',
        ],
        'J-Section': [
            '3.5mm J-Section White 3.00 Mtr JT003',
        ],
        'Low Profile Head Self Drilling Screw': [
            '4.2 x 25 Low Profile Self Drill Screw',
            '4.8 x 50 Low Profile Self Drill Screw',
        ],
        'Pencil Round Architrave': [
            '45 x 6 Pencil Round White PVC Architrave 5.00 Mtr',
        ],
        'Skirting': [
            '50mm Skirting (Rubber Seals) White 3.00 Mtr - SK011',
        ],
        'Two Part': [
            '40 x 12 H-Section Lid White 3.05 Mtr HS062',
        ],
    },
    'Plumbing': {
        '12mm Bore Reinforced Plastic Hose': [
            'Blue Reinforced Plastic Hose 12mm Bore x 3mm Wall 30Mtr Coil',
            'Red Reinforced Plastic Hose 12mm Bore x 3mm Wall 30Mtr Coil',
        ],
        '12mm x 100Mtr LLDPE Pushfit Pipe': [
            '12mm x 9mm x 100Mtr LLDPE Blue Pipe Pushfit',
            '12mm x 9mm x 100Mtr LLDPE Red Pipe Pushfit',
        ],
        'Air Admittance Valve': [
            'AV110 White 110mm Air Admittance Valve',
        ],
        'Barrier Pipe': [
            '15mm x 25Mtr White Barrier Pipe',
            '15mm x 3Mtr White Barrier Pipe',
            '15mm x 6Mtr Blue Barrier Pipe',
            '15mm x 6Mtr Red Barrier Pipe',
            '15mm x 6Mtr White Barrier Pipe',
            '22mm x 3Mtr White Barrier Pipe',
        ],
        'Brass Compression Nut & Olive': [
            '8mm Olive Brass',
        ],
        'Compressioned Ended Ball Valves': [
            '8mm Compression Ended Ball Valve c/w Yellow Insert',
        ],
        'Danfast Stamped Manifolds & Fittings': [
            '8mm Blanking Olive Brass 13780-8',
            'Connector 8mm x 3/8" BSPT Male Stud Brass',
            'Danfast 8mm 2 Way Stamped N/Pltd Manifold Set',
            'Danfast 8mm 3 Way Stamped N/Pltd Manifold Set',
            'Danfast 8mm 4 Way Stamped N/Pltd Manifold Set',
            'Elbow 90 Deg 8mm x 3/8" Male BSPT Brass',
        ],
        'Equal Elbow Brass Compression Fitting': [
            '10mm Equal Elbow Brass Compression Fitting',
            '15mm Equal Elbow Brass Compression Fitting',
            '8mm Equal Elbow Brass Compression Fitting',
        ],
        'Equal Straight Brass Compression Fitting': [
            '15mm Straight Coupling Brass Compression',
            '8mm Equal Straight Brass Compression Fitting',
        ],
        'Equal Tee Brass Compression Fitting': [
            '10mm Equal Tee Brass Compression Fitting',
            '15mm Equal Tee Brass Compression Fitting',
            '8mm Equal Tee Brass Compression Fitting',
        ],
        'Female Thread Brass Compression Fitting': [
            '10mm x 1/2" BSP Female Stud Brass Compression Fitting',
        ],
        'Foot Mounted Compression Ended Ball Valves': [
            '10mm Foot Mounted Compression Ended Ball Valve c/w Yellow Insert',
            '8mm Foot Mounted Compression Ended Ball Valve c/w Green Insert',
            '8mm Foot Mounted Compression Ended Ball Valve c/w Yellow Insert',
            '8mm Red Foot Mounted Ball Valve Compression Ended C/W',
        ],
        'General': [
            '15mm Brass Compression Non Return Valve',
            '15mm Double Check Valve Blk Pushfit',
            '15mm Double Check Valve DM Fit',
            '15mm Drain Cock Pushfit',
            '15mm End Stop Speedfit',
            '15mm Equal Elbow Connector Speedfit',
            '15mm Equal Straight Connector Speedfit',
            '15mm Equal Tee Connector Speedfit',
            '15mm Flexi Hose 300mm Pushfit Both Ends',
            '15mm Hand Valve Connector DM Fit (Black)',
            '15mm Pipe Clips - Snap On White Plastic',
            '15mm Service Valve DM Fit',
            '15mm Service Valve DMfit',
            '15mm Service Valve Speedfit',
            '15mm Stem Elbow Speedfit',
            '15mm Stop Valve DM Fit',
            '15mm Stop Valve Speedfit',
            '15mm Thermostatic Mixing Valve',
            '15mm x 1/2" BSP Female 300mm Flexi Hose Pushfit',
            '15mm x 1/2" id Hose Barb Conn Pushfit Blk',
            '22mm End Stop Pushfit Speedfit',
            '22mm Equal Elbow Connector Speedfit',
            '22mm Equal Straight Connector Speedfit',
            '22mm Equal Tee Connector Speedfit',
            '22mm Service Valve Speedfit',
            '22mm Stem Elbow Speedfit',
            '22mm Stop Valve DM Fit',
            '22mm Stop Valve Speedfit',
            '22mm x 1" Brass Female Cylinder Adaptor Speedfit',
            '22mm x 15mm x 15mm Reducing Tee Speedfit',
            '22mm x 15mm x 22mm Reducing Tee Speedfit',
            '22mm x 22mm x 15mm Reducing Branch Tee Speedfit',
            '250ml Solvent Cement',
            'Plastic Pipe Cutter (up to 28mm)',
            'SP300 Grey Weathering Collar 110mm',
            'TB37 White 32mm x 76mm Seal Waste Bottle Trap',
            'TB47 White 40mm x 76mm Seal Waste Bottle Trap',
            'TP37 White 32mm x 76mm Swivel P Trap',
            'TP47 White 40mm x 76mm Swivel P Trap',
            'TS47 White 40mm x 76mm Seal S Trap',
            'WT64PV White 32mm x 75mm P Trap Telescopic Anti-Syphon',
        ],
        'Hose Clips, Worm Drive': [
            'Hose Clips 1" - 1.3/8" M/S 1 (25mm - 35mm)',
            'Hose Clips 1/2" - 3/4" M/S 00 (13mm - 20mm)',
            'Hose Clips 1/2" - 5/8" M/S M00 (11mm - 16mm)',
            'Hose Clips 3/4" - 1" M/S 0X (18mm - 25mm)',
            'Hose Clips 3/8" - 1/2" M/S 000 (9.5mm - 12mm)',
            'Hose Clips 5/8" - 7/8" M/S 0 (16mm - 22mm)',
            'Hose Clips 7/8" - 1.1/8" M/S 1A (22mm - 30mm)',
        ],
        'Knuckle Bend': [
            'WP10 White 32mm Knuckle Bend',
            'WP11 Grey 40mm Knuckle Bend',
            'WP11 White 40mm Knuckle Bend',
        ],
        'Macerators': [
            'Sanibest Pro Macerator Pump',
            'Saniflo Sanicom 1 Macerator Pump',
            'Saniflo Sanicubic 1 Macerator Pump',
            'Sanispeed+ Waste Water Pump',
        ],
        'Misc Gas': [
            'Gas Bottle Strap Kit 1200mm c/w Bracket & Spacer',
        ],
        'Obtuse Bend 45°': [
            'WP18 White 32mm Obtuse Bend 45 Degree',
            'WP19 White 40mm Obtuse Bend 45 Degree',
        ],
        'Pipe Clip': [
            'WP34 White 32mm Pipe Clip',
            'WP35 White 40mm Pipe Clip',
        ],
        'Pipe Insulation': [
            '15mm x 9mm x 1Mtr Grey Pipe Insulation',
            '22mm x 9mm x 1Mtr Grey Pipe Insulation',
        ],
        'Pipe Support': [
            '15mm Double Seal Pipe Support Sleeve Pushfit Blk',
            '15mm Pipe Support Pushfit Sleeve Blk',
            '22mm Pipe Support Sleeve Pushfit Blk',
        ],
        'Plastic Pipe Clips': [
            '15mm Plastic Pipe Clips',
            '22mm Plastic Pipe Clips',
        ],
        'Plastic Pipe Collars': [
            '110mm Pipe Collar White Plastic',
            '15mm Pipe Collar Chrome Finish',
            '15mm Pipe Collar White Plastic',
            '35mm Pipe Collar White Plastic',
            '42mm Pipe Collar White Plastic',
        ],
        'Pushfit Equal Elbow': [
            '12mm Equal Elbow Connector Pushfit',
        ],
        'Pushfit Equal Straight': [
            '12mm Equal Straight Connector Pushfit',
        ],
        'Pushfit Equal Tee': [
            '12mm Equal Tee Connector Pushfit',
        ],
        'Pushfit Fittings': [
            '12mm Divider Pushfit',
            '12mm x 1/2"BSP Female Adapter Pushfit',
        ],
        'Pushfit Stem Elbow': [
            '12mm Stem Elbow Pushfit',
        ],
        'Pushfit Stem Reducer': [
            '15mm Stem x 12mm Tube Reducer DMfit',
        ],
        'Pushfit Unequal Straight': [
            '12mm x 10mm Straight Reducing Coupling Pushfit',
            '15mm x 12mm Straight Reducing Coupling DMfit',
        ],
        'Rainwater Pipe & Fittings': [
            'RBS5 White 25-67mm Adjustable Offset Bend',
        ],
        'Reducer': [
            'WP38 White 40mm x 32mm Reducer',
        ],
        'Rubber Boss Adaptor': [
            'SP10 Black 32mm Boss Adaptor (Rubber Push Fit)',
            'SP11 Black 40mm Boss Adaptor (Rubber Push Fit)',
        ],
        'Soil Pipe': [
            'SP1 White 110mm x 3Mtr Pipe Plain Ends',
            'SP3 Grey 110mm Single Socket Soil Pipe 3Mtr',
            'SP3 White 110mm Single Socket Soil Pipe 3Mtr',
        ],
        'Soil Pipe Clips': [
            'SP82 Grey 110mm Plastic Pipe Clip',
            'SP82 White 110mm Plastic Pipe Clip',
        ],
        'Soil Single Branch Tee 92.5°': [
            'SP190 Grey 110mm Single Branch Tee 92.5 Degree (2Boss)',
            'SP190 White 110mm Single Branch Tee 92.5 Degree (2Boss)',
        ],
        'Solvent Weld Knuckle Bend': [
            'WS10 White 32mm Solvent Weld Knuckle Bend',
            'WS11 White 40mm Solvent Weld Knuckle Bend',
            'WS12 White 50mm Solvent Weld Knuckle Bend',
        ],
        'Solvent Weld Obtuse Bend': [
            'WS18 White 32mm Solvent Weld Obtuse Bend',
            'WS19 White 40mm Solvent Weld Obtuse Bend',
            'WS20 50mm White Solvent Weld Obtuse Bend',
        ],
        'Solvent Weld Pipe': [
            'WS01 White 32mm x 3Mtr Solvent Weld Waste Pipe',
            'WS02 White 40mm x 3Mtr Solvent Weld Waste Pipe',
            'WS03 White 50mm x 3Mtr Solvent Weld Waste Pipe',
        ],
        'Solvent Weld Pipe Clip': [
            'WS34 White 32mm Solvent Weld Pipe Clip',
            'WS35 White 40mm Solvent Weld Pipe Clip',
            'WS36 White 50mm Solvent Weld Pipe Clip',
        ],
        'Solvent Weld Reducer': [
            'WS38 White 40mm x 32mm Reducer Solvent Weld',
            'WS39 White 50mm x 32mm Reducer Solvent Weld',
            'WS40 White 50mm x 40mm Reducer Solvent Weld',
        ],
        'Solvent Weld Screwed Access Plug': [
            'WS30 White 32mm Screwed Access Plug Solvent Weld',
            'WS31 White 40mm Screwed Access Plug Solvent Weld',
        ],
        'Solvent Weld Straight Coupling': [
            'WS07 White 32mm Solvent Weld Straight Coupling',
            'WS08 White 40mm Solvent Weld Straight Coupling',
            'WS09 White 50mm Solvent Weld Straight Coupling',
        ],
        'Solvent Weld Tee': [
            'WS22 White 32mm Solvent Weld Swept Tee',
            'WS23 White 40mm Solvent Weld Swept Tee',
            'WS24 White 50mm Solvent Weld Swept Tee',
        ],
        'Solvnet Weld Swivel Bend': [
            'WS26 White 32mm Solvent Weld Swivel Bend',
            'WS27 White 40mm Solvent Weld Swivel Bend',
            'WS28 White 50mm Solvent Weld Swivel Bend',
        ],
        'Spare Valve Blades': [
            'Gas Manifold Blade Blue',
            'Gas Manifold Blade Green',
            'Gas Manifold Blade Red',
            'Gas Manifold Blade White',
        ],
        'Sparge Pipes (Exposed) Top Inlet': [
            'Range Of 2 Sparge Pipes (Exposed) Top Inlet',
            'Range Of 3 Sparge Pipes (Exposed) Top Inlet',
            'Range Of 4 Sparge Pipes (Exposed) Top Inlet',
        ],
        'Straight Coupling': [
            'WP07 White 32mm Straight Coupling',
            'WP08 White 40mm Straight Coupling',
        ],
        'Strap On Boss Clip': [
            'SP319 Grey 110mm Soil Strap Boss',
            'SP319 White 110mm Soil Strap Boss',
        ],
        'Swept Elbow': [
            'WP14 White 32mm Swept Elbow',
            'WP15 White 40mm Swept Elbow',
        ],
        'Swept Tee': [
            'WP22 White 32mm Swept Tee',
            'WP23 White 40mm Swept Tee',
        ],
        'Unequal Elbow Brass Compression Fitting': [
            '22mm x 15mm Elbow Brass Compression Fitting',
        ],
        'Unequal Straight Brass Compression Fitting': [
            '10mm x 8mm Straight Brass Compression Fitting',
            '15mm x 10mm Straight Brass Compression Fitting',
            '15mm x 8mm Straight Brass Compression Fitting',
            '22mm x 15mm Straight Brass Compression Fitting',
        ],
        'Unequal Tee Brass Compression Fitting': [
            '10mm x 10mm x 8mm Unequal Tee Brass Fitting Branch Reduced',
            '22mm x 15mm x 15mm Unequal Tee Brass Compression Fitting',
        ],
        'Waste Pipe': [
            'WP01 White 32mm Waste Pipe x 3Mtr',
            'WP02 Grey 40mm Waste Pipe x 3Mtr',
            'WP02 White 40mm Waste Pipe x 3Mtr',
        ],
        'Waste Pipe & Fittings': [
            'Convoluted Hose Sealing Sleeve 23.5mm id',
            'Grey Convolute Polyprop Hose 23.5mm id, 50Mtr Coil',
        ],
        'Water Pumps': [
            'DAB Jetinox 82M Control-D 220-240v 50Hz Water Pump',
            'Stuart Turner Brass Pump Body For Boostmatic Pump',
        ],
        'Water Pumps 12v/24v': [
            'Comet Eco-Plus 12V 13Ltr Submersible Pump',
        ],
        'Whale Watermaster Pump': [
            'Whale Hose Barb Stem Adaptor 15mm x 1/2" Barb',
            'Whale Watermaster 12v Pump 11.5ltr 30psi c/w filter',
            'Whale Watermaster 12v Pump 11.5ltr 45psi c/w filter',
            'Whale Watermaster 24v Pump 11.5ltr 45psi c/w filter',
        ],
    },
    'Space Heating': {
        'Downflow Heaters': [
            '*Stiebel CK 20 Premium 2kw Downflow Heater',
            'Consort BFH2E 2kw Downflow Heater Metal Body',
            'Consort DF2E 2kw Downflow Heater With 7 Day 24/7 Timer',
            'Stiebel CK 20 Trend 2kw Downflow Heater',
        ],
        'Drying Room': [
            'Replacement Filter for TTK170 Dehumidifier',
            'Replacement Tank For TTK170 Dehumidifier',
            'Trotec TTK170Eco Dehumidifier c/w Fixing Bracket',
        ],
        'Heaters': [
            'Consort 3kW High Level Fan Heater Wireless Control c/w Flex',
            'Consort BFH2SL Downflow 2kW Metal Bodied Wireless',
            'Consort PSL200T 2kW Panel Heater Wireless c/w Thermostat',
        ],
        'Oil Filled Heaters': [
            '2kW Column Oil Filled Radiator c/w Timer',
        ],
        'Panel Heaters': [
            'Consort PLE150 1.5kW Panel Heater c/w 7 Day Electronic Timer',
            'Consort PVE200 2kw Panel Heater c/w Electronic 7 Day',
        ],
        'Single Tubular Heater': [
            '2ft Single Tubular Heater 80W White',
            '3ft Single Tubular Heater 135W White',
            '4ft Single Tubular Heater 180W White',
        ],
        'Space Heating': [
            'Heatsource Single Outlet Vehicle Heater HS2000/V1-D',
            'Heatsource Twin Outlet Marine Heater HS2000/12/M2',
        ],
        'Stiebel CNS-U LCD Panel Heaters': [
            'Stiebel CNS-U 1000 Plus LCD 1KW Panel Heater',
            'Stiebel CNS-U 2000 Plus LCD 2kw Panel Heater',
        ],
        'Tubular Heater Guard': [
            'Guard To Suit 2ft Tubular Heater',
            'Guard To Suit 3ft Tubular Heater',
            'Guard To Suit 4ft Tubular Heater',
        ],
    },
    'Tools & Consumables': {
        '25mm Pozi Bits': [
            'No 1 Pozi Insert Bit 1/4 Hex 25mm',
            'No 2 Pozi Insert Bit 1/4 Hex 25mm',
            'No 3 Pozi Insert Bit 1/4 Hex 25mm',
        ],
        'Abrasive Rolls': [
            'Abrasive Roll 120 Grit x 115mm 50Mtr Roll',
            'Abrasive Roll 80 Grit x 115mm 50Mtr Roll',
        ],
        'Aluminium Stencil Sets': [
            'Stencil Set 0-9 Flat Plate Aluminium 50mm',
            'Stencil Set A-Z Flat Plate Aluminium 50mm',
        ],
        'Cleaning Products': [
            'Bleach 5 litre',
            'Detergent 15% 5 litre',
            'Pine Disinfectant 5 litre',
            'Selden Blast Air Freshener Cranberry 750ml',
            'Selden S Lemon Industrial Maintenance Cleaner',
            'Selden Stainless Steel Cleaner And Polish 750ml',
            'Selden Traffic Film Remover 5 Litre',
        ],
        'Cobalt Ground Flute Drill Bits': [
            '3mm Ground Flute Cobalt Drill',
            '4mm Ground Flute Cobalt Drill',
            '5mm Ground Flute Cobalt Drill',
            '6mm Ground Flute Cobalt Drill',
            '8mm Ground Flute Cobalt Drill',
        ],
        'Disposable Gloves': [
            'Blue Powder Free Nitrile Gloves - Extra Large (Box 100)',
            'Blue Powder Free Nitrile Gloves - Large (Box 100)',
        ],
        'General': [
            '400ml Multi Spray',
            'Gloves Canadian Style Riggers (Pair)',
            'Magnetic Bit Holder',
            'Microfibre Cleaning Cloth 380G (Pack Of 10)',
            'No 2 Philips Bit 1/4 Hex',
        ],
        'HSS Flute Ground Jobber Drill Bits': [
            '10mm HSS Flute Ground Jobber Drills',
            '12.5mm HSS Flute Ground Jobber Drills',
            '2.5mm HSS Flute Ground Jobber Drills',
            '2mm HSS Flute Ground Jobber Drills',
            '3.5mm HSS Flute Ground Jobber Drills',
            '3mm HSS Flute Ground Jobber Drills',
            '4.5mm HSS Flute Ground Jobber Drills',
            '4mm HSS Flute Ground Jobber Drills',
            '5.5mm HSS Flute Ground Jobber Drills',
            '5mm HSS Flute Ground Jobber Drills',
            '6mm HSS Flute Ground Jobber Drills',
            '7mm HSS Flute Ground Jobber Drills',
            '8mm HSS Flute Ground Jobber Drills',
        ],
        'Misc Essentials': [
            'Adaptable Box 100 x 100 x 50mm Galvanised',
            'Weatherproof Plexo Box (IP56) 100 x 100 x 50mm',
        ],
        'PVC Sleeving': [
            '3mm PVC Sleeving Green/Yellow 100M Coil',
        ],
    },
    'Ventilation & Vents': {
        '170 x 90 BS Louvre Vent': [
            'Ivory Louvre Int. Vent 170 x 90 NCC Approved',
            'Larch Louvre Int. Vent 170 x 90 NCC Approved',
            'Mosaic-Beige Louvre Int. Vent 170 x 90 NCC Approved',
            'White Louvre Int Vent 170 x 90 NCC Approved',
        ],
        'Aluminium Louvre Vent': [
            '6.5" x 3.5" Fixed Louvre Alloy Vent Without Flyscreen',
            '9.5" x 3.5" Fixed Louvre Alloy Vent Without Flyscreen',
            '9.5" x 6.5" Fixed Louvre Alloy Vent Without Flyscreen',
        ],
        'External Grill Vent': [
            '100mm/4" External Gravity Grille Vent',
            '150mm/6" External Gravity Grille Vent',
        ],
        'External Wall Grille': [
            '100mm/4" Ext Wall Grille White',
            '150mm/6" Ext Wall Grille White',
        ],
        'Extractor Fans': [
            '100mm/4" Extractor Fan c/w Timer',
            '100mm/4" Pull Cord Extractor Fan',
            '150mm/6" Extractor Fan c/w Timer & Shutters',
        ],
        'General': [
            '10A 3 Pole Fan Isolator Switch',
            'Air Break (Back Flow Preventer) 15mm/22mm UC00/001',
            'Grill Vent White 6.3/4"x3.1/2"',
            'Louvre Vent White 9.1/2" x 3.1/2"',
            'Vent Hexagon White 2.3/4"',
        ],
        'Map Plastic Louvre Vent with Flyscreen': [
            'Vent Map Louvre White 6" x 3" With Flyscreen',
            'Vent Map Louvre White 9" x 6" With Flyscreen',
        ],
        'Soffit Vent': [
            '90mm Dia Brown Plastic Soffit Vent',
            '90mm Dia White Plastic Soffit Vent',
        ],
    },
    'Washroom': {
        '40mm Staple Skirting SK003': [
            '40mm Staple Skirting White 3.00 Mtr SK003',
        ],
        'Accessories': [
            '12" x 9" Mirror, Drilled 2 Holes Polished Edges, Safety Backed',
            'SAA Toilet Roll Holder',
            'Toilet Indicator Bolt SAA',
            'Toilet Roll Holder Inserts Black',
        ],
        'Bathroom': [
            'Contessa Vanity Cabinet White',
        ],
        'Complete WC Components': [
            'Dudley Acclaim V Push Button Dual Flush Cistern BIIO L/L',
            'Dudley Contract Slimline Dual Flush Lever Cistern SIIO RH Inlet',
            'Flush Pipe Internal Cone Clear',
            'SK57 White 110mm Flexi Pan Connector',
            'SP101 White 110mm Kwickfit Straight Pan Connector',
            'SP102 White Kwickfit Offset Pan Connector 110mm',
            'SP103 White 110mm Pan Connector 90Deg (225mm Leg)',
            'White Low Level Lever Plastic Cistern SIIO',
            'White Low Level WC Pan',
        ],
        'Compression Elbow': [
            'WC10 White 32mm Unicom Equal Elbow',
            'WC11 White 40mm Unicom Equal Elbow',
        ],
        'Compression Straight Coupling': [
            'WC07 White 32mm Unicom Straight Coupling',
            'WC08 White 40mm Unicom Straight Coupling',
        ],
        'Compression Tee': [
            'WC22 White 32mm Unicom Equal Tee',
            'WC23 White 40mm Unicom Equal Tee',
        ],
        'Danfast Stamped Manifolds & Fittings': [
            'Taper Plug 3/8" BSPT Male N/Pltd',
        ],
        'Dudley Auto Cistern': [
            'Dudley 1 Gallon Auto Cistern White',
            'Dudley 2 Gallon Auto Cistern White',
        ],
        'Flexi Tail Barb Connection': [
            'Comet Florenz Single Tap CP c/w 1/2" Barb Flexi Tails',
        ],
        'Flexi Tail Pushfit Connection': [
            'Comet Florenz Mixer Tap CP c/w 12mm Push Fit Connections',
            'Comet Florenz Single Tap CP c/w 12mm Push Fit Connections',
        ],
        'Flooring': [
            '50mm Hazard Warning Anti-Slip Adhesive Tape 18.3Mtr',
        ],
        'General': [
            '15mm Emergency Shut Off Tap Speedfit',
            '15mm Stop Tap Brass Compression Ended',
            '15mm Straight Washing Machine Tap',
            '15mm X 3/4" X 300mm Flexi Hose Tap Connection',
            '15mm x 1/2" BSP Tap Connector Straight Speedfit',
            '15mm x 1/2"BSP Bent Tap Connector Brass Nut Speedfit',
            '15mm x 1/2"BSP Bent Tap Connector Steel Nut DM Fit',
            '15mm x 1/2"BSP Straight Tap Connector Steel Nut DM Fit',
            '15mm x 1/2"BSP Tap Connector (Plastic Nut) DM Fit',
            '15mm x 3/4"BSP Tap Connector (Plastic Nut) DM Fit',
            'Mcalpine Shower Waste BSW9P-F Centre Pin',
            'Non Concussive Exposed Shower Valve',
            'PTFE Tape Rolls (Water)',
            'WC38 White 40mm x 32mm Unicom Straight Reducer',
        ],
        'Hand Dryers': [
            'ATC Cub Hand Dryer White',
            'Hurricane 1.8kW Automatic Hand Dryer',
            'Paper Hand Towel 1 Ply Z Fold Blue Re-Cycled (15Pks x 200)',
            'Paper Towel Dispenser',
        ],
        'Kinedo Consort Shower Cubicle': [
            'Consort Shower Cubicle 810 x 810mm',
        ],
        'Masking Tape': [
            '24mm x 50Mtr Pro Masking Tape',
            '48mm x 50Mtr Pro Masking Tape',
        ],
        'Misc Gas': [
            'Arctic Gas Identification Tape',
            'Roll PTFE Tape Gas BSEN 751 Part 3',
        ],
        'PVC Insulation Tape': [
            'Black PVC Insulation Tape 19mm x 20M',
            'Blue PVC Insulation Tape 19mm x 20M',
            'Brown PVC Insulation Tape 19mm x 20M',
            'Green/Yellow PVC Insulation Tape 19mm x 20M',
            'Red PVC Insulation Tape 19mm x 20M',
        ],
        'Puma Toilet Seat': [
            'Black Toilet Seat Puma',
            'White Toilet Seat Puma',
        ],
        'Redring Pure Electric Shower': [
            '7.5kW Pure Instantaneous Electric Shower',
            '8.5kW Pure Instantaneous Electric Shower',
        ],
        'Showers & Cubicles': [
            '800mm x 800mm Shower Tray 30mm Depth Includes 90mm Waste',
            '90mm Fast Flow Shower Waste Chrome',
            'Shower Curtain Rings (Pack 12)',
            'White Shower Curtain',
        ],
        'Sink Base Unit Kit': [
            'Chrome High Neck Pillar Taps',
            'Chrome Taphole Stopper Plastic',
        ],
        'Swivel': [
            'Thetford C223CS Swivel Toilet 12V Flush (OEM) Bulk',
        ],
        'Taps & Wastes': [
            '1.1/4" x 3.1/2" Chrome Slotted Waste For 45cm & 56cm Basins',
            '1/2" Brass Backnut 39mm Flange',
            '1/2" Top Hat Washer (Pack Of 100)',
            'Basin Taps Chrome Plated (pair)',
            'Mcalpine Basin Waste 1.1/4 BSW1Pt',
            'Non Concussive Basin Taps (Pair)',
            'Non Concussive Basin Taps (Pairs) - NCT001',
            'Sink Waste Chain And Stay 12"',
        ],
        'Urinals & Accessories': [
            '1.1/2" Plastic Wastes To Suit Urinal',
            '1.1/2" St/St Dome Unslotted Urinal Waste',
            '50cm Urinal Bowl White',
            'Cistermiser - 1/2" BSP Female Thread',
            'Top Inlet Urinal Spreader, Fixing Stud, Nut & Washer',
            'Urinal Bracket (Pair)',
        ],
        "WC's": [
            'Cistern Lever Assembly Pack',
            'Close Coupled Doc M Kit (LABC Approved)',
            'Disabled Toilet Alarm Kit',
        ],
        'Wash Basins': [
            '*555mm 2-Taphole Washbasin White - Atlas',
            '12" Cast Iron Towel Rail Brackets (Pair)',
            '459mm 2 taphole White Washbasin',
            '590mm 2 taphole White Washbasin',
            'Basin Brackets (Pair) For Wall Hung 459mm Basin',
            'Dudley Support Bracket (Single)',
            'Dudley Support Leg (Single)',
            'Full Pedestal To Suit Atlas Washbasin',
        ],
        'Waterless Urinals': [
            'Saracen Powerballs To Suit Waterless Urinal System (Pack/50)',
            'Saracen Waterless Maintenance Pack c/w Cleaner & 3 Powerballs',
            'Saracen Waterless Urinal Installation Pack',
        ],
    },
    'Water Heating': {
        'Catering Boilers': [
            '*Hyco Water Filter F2ST for Microboil/Omega',
            '*Hyco Water Filter Spare Cart F2STCAR for Microboil/Omega',
            'Catering Urn St/St',
        ],
        'Frost Protection': [
            'Hyco Mojave Frost Protector',
        ],
        'Hand Dryers': [
            '*Hyco Blade 1.6kw Automatic Hand Dryer',
            'Hyco Arc Hand Dryer',
            'Hyco Prism Hand Dryer',
        ],
        'Handwash': [
            'Hyco Wave 3kW Instantaneous Hand Wash Automatic',
            'Hyco Wave 3kW Instantaneous Hand Wash Manual',
            'Hyco Wave PRV Repair Kit incl. Silicone Balls & Tool',
            'Maxima Hand Soap Perfumed Pink 5Ltr',
            'Redring Instant 3kw Automatic Hand Wash Unit',
            'Redring Instant 3kw Manual Hand Wash Unit',
            'Soap Dispenser Bulk Fill',
            'Triton 3kW Hand Wash Unit',
        ],
        'Hyco Accona Panel Heater c/w 7 Day Digital Timer': [
            'Hyco Accona 1.5kW Panel Heater c/w 7 Day Digital Timer',
            'Hyco Accona 2kW Panel Heater c/w 7 Day Digital Timer',
        ],
        'Hyco Microboil Smart Boiling Water Heater': [
            'Hyco MS3W Microboil Smart 3L Water Heater 20Cup',
            'Hyco MS6W Microboil Smart 6L Water Heater 38Cup',
        ],
        'Over Sink Water Heaters': [
            'Handyflow 2kW 5L Water Heater Auto Reset',
            'Stiebel Eltron Water Heater Oversink SN5 5Ltr',
            'Zip Tudor Water Heater 2kw 5.5 Litre',
        ],
        'Powerflow Water Heaters': [
            'Hyco Powerflow Smart 30Ltr Unvented Multipoint Water Heater',
        ],
        'Speedflow 2kW Undersink Water Heater': [
            'Speedflow 2kW 15L Water Heater Undersink Unvented',
        ],
        'Speedflow v2 Undersink Water Heater': [
            'Hyco Speedflow 10ltr 1.2kw Undersink Water Heater',
            'Hyco Speedflow 10ltr 2kw Undersink Water Heater',
            'Hyco Speedflow 15ltr 1.2kw Undersink Water Heater',
            'Hyco Speedflow 5ltr 2kw Undersink Water Heater',
        ],
        'Under Sink Water Heaters': [
            'Handyflow 5Ltr Undersink Water Heater 2kW c/w Vented Tap',
        ],
        'Water Heater Spares': [
            '2Ltr Expansion Vessel And Check Valve To Suit Speedflow SF3',
            'Expansion Vessel Kit For Speedflow SF4',
            'Hyco Handyflow Spout Only',
            'Hyco Spare Tap To Suit Handyflow Oversink Water Heater',
            'Hyco Vented Tap For Handyflow Undersink Water Heater',
            'Pressure Reducing Valve 15mm SF5',
            'Thermal Cut Out To Suit Santon A7/3 & Elson EOS7',
        ],
        'Water Heating': [
            'Malaga 5E Caravan Water Heater c/w Remote Switch (LPG/Mains)',
            'Propex Storage Water Heater 6L',
        ],
    },
}

# Non-Danfast lanes: timber and sheet from BBM and Timb-Ply, bulk
# paint from Manor, signage from Pinnacle (item names drawn from the
# invoice history so the PO worker prices them where it can).
OTHER_CATEGORIES = {
    "Timber & Sheet Materials": [
        "3x2 CLS Timber", "4x2 CLS Timber", "2x2 Timber",
        "Treated Battens 25x50mm", "18mm OSB3 Board 2440x1220",
        "9mm OSB3 Board 2440x1220", "18mm Plywood 2440x1220",
        "12mm Plywood 2440x1220", "Hardwood Ply Class 2",
        "CSM10 White Ceiling Boards", "3mm Wall Boards",
        "JCOP Boards", "MDF Sheet", "Windows", "Worktops",
        "Base Units", "Shutters",
    ],
    "Bulk Paint": [
        "Kensite Green Paint", "White Paint", "Primer",
        "Customer Colour Paint (put the colour in notes)",
    ],
    "Signage & Graphics": [
        "Printed Signage", "Cabin Graphics", "Stickers / Decals",
        "Printed Boards",
    ],
}
ANYTHING_ELSE = "Anything Else"
OTHER_ITEM = "Other / not listed"

# category order and emoji for the picker: most-used trades first
FORM_CAT_LABELS = {
    "Plumbing": "🚰 Plumbing",
    "Electrical": "🔌 Electrical",
    "Space Heating": "🔥 Space Heating",
    "Water Heating": "♨️ Water Heating",
    "Washroom": "🚿 Washroom",
    "Doors & Security": "🚪 Doors & Security",
    "Fastenings & Fixings": "🔩 Fastenings & Fixings",
    "Timber & Sheet Materials": "🪵 Timber & Sheet Materials",
    "Lighting": "💡 Lighting",
    "Flooring": "🟫 Flooring",
    "Plastics & Profiles": "📐 Plastics & Profiles",
    "Adhesives & Sealants": "🧴 Adhesives & Sealants",
    "Canteen & Furniture": "🍽 Canteen & Furniture",
    "Ventilation & Vents": "🌬 Ventilation & Vents",
    "Fire Safety": "🧯 Fire Safety",
    "Guttering & Roofline": "🏠 Guttering & Roofline",
    "Painting & Decorating": "🖌 Painting & Decorating",
    "Bulk Paint": "🎨 Bulk Paint",
    "Signage & Graphics": "🪧 Signage & Graphics",
    "Tools & Consumables": "🧰 Tools & Consumables",
    "General & Misc": "📦 General & Misc",
    "Anything Else": "❔ Anything Else",
}
FORM_CATEGORY_ORDER = [c for c in FORM_CAT_LABELS
                       if c in DANFAST_TREE or c in OTHER_CATEGORIES
                       or c == ANYTHING_ELSE]

TYPE_STYLE = {
    "On Hire":      (K_GREEN_PALE, K_GREEN_DARK, "●"),
    "Off Hire":     ("#fdecea",    "#7b1a1a",    "●"),
    "Site Move":    ("#eef2ff",    "#2d3a8c",    "●"),
    "Site Visit":   ("#f3e8ff",    "#5b21b6",    "●"),
}
K_PURPLE      = "#7c3aed"
K_PURPLE_PALE = "#f3e8ff"
K_PURPLE_DARK = "#5b21b6"

# ── Password protection ───────────────────────────────────────────────────────
if not st.session_state.get("authenticated", True):
    st.session_state["authenticated"] = True

# Auto-refresh every 10 seconds — paused when a file is uploading OR any dialog is open
# (Nathan, 16/08/2026: was 30 seconds. The cache TTLs below were dropped
# to 10 to match; leaving them at 30 would have meant two refreshes in
# every three redrawing the same cached data.)
_file_uploading  = st.session_state.get("lh_uploader") is not None
_any_dialog_open = st.session_state.get("any_dialog_open", False)
if not _file_uploading and not _any_dialog_open:
    st_autorefresh(interval=10_000, limit=0, key="schedule_autorefresh")

# ── GitHub config ─────────────────────────────────────────────────────────────
GITHUB_TOKEN  = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO   = st.secrets["GITHUB_REPO"]
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
DATA_FILE     = "data/jobs.json"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}",
           "Accept": "application/vnd.github.v3+json"}

def gh_get(path):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    r = requests.get(url, headers=HEADERS, params={"ref": GITHUB_BRANCH},
                     timeout=10)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    d = r.json()
    return json.loads(base64.b64decode(d["content"]).decode()), d["sha"]

def gh_put(path, obj, sha=None, msg="Update schedule"):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    payload = {"message": msg,
               "content": base64.b64encode(json.dumps(obj, indent=2).encode()).decode(),
               "branch": GITHUB_BRANCH}
    if sha:
        payload["sha"] = sha
    requests.put(url, headers=HEADERS, json=payload,
                 timeout=15).raise_for_status()

# load_request_file is unused since the request panels came out (09/10/2026);
# kept for the Archive copy of the panels, which calls it.
@st.cache_data(ttl=30)
def load_request_file(path):
    """Cached read of a request-queue file: one GitHub call per file per
    30s across every rerun and session, instead of one per rerun. Writers
    must call load_request_file.clear() after a successful gh_put so the
    change shows immediately.

    09/10/2026: the TTL went from 10s to 30s. The whole NathanMTCO GitHub
    account shares 5,000 calls an hour and ran out each hour on 09/10,
    failing every automation that touches GitHub for the last minutes of
    the hour. At 10s this app alone was 24 calls a minute (four files),
    about 1,440 an hour; at 30s it is 480. The page still reruns every
    10s, so a change made at this desk shows at once (the writer clears
    the cache) and a change made elsewhere shows within 30s."""
    return gh_get(path)

@st.cache_data(ttl=30)
def load_data():
    data, sha = gh_get(DATA_FILE)
    if data is None:
        return {}, {}, {}, {}, {}, {}, {}, {}, {}, None
    return (data.get("jobs", {}), data.get("mcs", {}),
            data.get("site_visits", {}), data.get("svr_confirmed", {}),
            data.get("checklist", {}), data.get("live_hire", {}),
            data.get("materials", {}), data.get("materials_totals", {}),
            data.get("queries", {}), sha)

def _job_identity(j):
    """Identity used to spot the same job in two copies of the data."""
    return (str(j.get("contract_number") or "").strip(),
            j.get("type", ""), j.get("customer", ""), j.get("postcode", ""))

_MERGE_WINDOW_MIN = 10

def _recently_created(j):
    """True if the job was created within the merge window."""
    try:
        ts = datetime.strptime(j.get("timestamp", ""), "%d/%m/%Y %H:%M")
        return datetime.now() - ts <= timedelta(minutes=_MERGE_WINDOW_MIN)
    except Exception:
        return False

# Fields on a materials line that belong to Ken (the PO worker), not to
# this app. The app must never write an older value of these over a
# newer one.
#
# 17/08/2026: it did exactly that. Ken raised PO 01988 for Mitch at
# 13:25 and PO 01990 for Cliff at 13:35, stamped both onto their lines,
# and emailed Chris. Somebody then used the app with a session whose
# copy of jobs.json predated the stamp; save_data wrote the whole
# materials dict back from that stale copy and the stamps vanished.
# Both requests went back to red, and because the approval sweep looks
# for lines carrying po_number, neither could ever flip to Ordered
# again. Jim's 13:30 and Alex's 13:40 survived only because nobody
# happened to save in those two windows.
#
# The jobs key was already protected by the merge above. Everything
# else was not.
# The exact field names Ken stamps in stamp_lines(). DELIBERATELY NOT
# LISTED: delivered, status, ordered_by, query_answer. The app writes
# all four itself - the Delivered button and its untick, the
# mark-as-ordered button, and the Yes/No answers to Ken's queries.
# Letting the fresh copy win on those would make an untick spring back,
# which is a worse bug than the one being fixed. Only fields the app
# never authors are protected here.
_WORKER_FIELDS = ("po_number", "po_status", "po_supplier", "po_link",
                  "po_order_id", "query", "query_candidate")


def _recently_created_line(rec):
    """Same idea as _recently_created, for a materials or live hire line,
    which stamps created_at rather than timestamp."""
    for field in ("created_at", "timestamp"):
        raw = rec.get(field, "")
        for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S"):
            try:
                ts = datetime.strptime(raw, fmt)
                return datetime.now() - ts <= timedelta(
                    minutes=_MERGE_WINDOW_MIN)
            except Exception:
                continue
    return False


def _protect_worker_fields(payload_obj, fresh_obj):
    """Never let this session's copy of a materials line undo something
    Ken wrote while the page was sitting open.

    materials and live_hire are FLAT dicts keyed by line id, so this
    walks ids, not dates. For a line in both copies, any worker field
    present in the fresh one wins. A line that exists only in the fresh
    copy is carried over whole, so a line added since the page loaded is
    not dropped on save.
    """
    for key in ("materials", "live_hire"):
        fresh_map = fresh_obj.get(key)
        local_map = payload_obj.get(key)
        if not isinstance(fresh_map, dict) or not isinstance(local_map, dict):
            continue
        for lid, fresh_rec in fresh_map.items():
            if not isinstance(fresh_rec, dict):
                continue
            mine = local_map.get(lid)
            if not isinstance(mine, dict):
                # Missing locally. That is either a line someone else
                # added since this page loaded, or one this session
                # deliberately deleted. Only the first is restored, on
                # the same recency test the jobs merge uses, so a
                # genuine delete is still honoured.
                if _recently_created_line(fresh_rec):
                    local_map[lid] = fresh_rec
                continue
            for f in _WORKER_FIELDS:
                if f in fresh_rec and fresh_rec.get(f) not in (None, ""):
                    mine[f] = fresh_rec[f]
        payload_obj[key] = local_map


def save_data(jobs_dict, mcs_dict, sv_dict=None, svr_dict=None,
              cl_dict=None, lh_dict=None, mat_dict=None, matt_dict=None, _sha_hint=None):
    """Fetch latest data immediately before writing and merge in any jobs
    created remotely in the last few minutes that this session has not seen
    (e.g. by the MCS auto-add script or another user). Prevents a save from
    a slightly stale session silently wiping fresh additions, while still
    honouring deletions of anything older. Retries on write conflicts."""
    payload_obj = {
        "jobs":          jobs_dict,
        "mcs":           mcs_dict,
        "site_visits":   sv_dict  or {},
        "svr_confirmed": svr_dict or {},
        "checklist":     cl_dict  or {},
        "live_hire":     lh_dict  or {},
        "materials":     mat_dict or {},
        "materials_totals": matt_dict or {},
        # Yard job queries. Read from the module global rather than passed
        # in, so every existing save_data call keeps working unchanged.
        "queries":       globals().get("queries") or {},
    }
    load_data.clear()   # scoped: keep the bank-holiday + queue caches
    for attempt in range(3):
        fresh_obj, fresh_sha = gh_get(DATA_FILE)
        if fresh_obj:
            local_jobs = payload_obj["jobs"]
            for dkey, remote_list in (fresh_obj.get("jobs") or {}).items():
                local_keys = {_job_identity(x) for x in local_jobs.get(dkey, [])}
                for rj in remote_list or []:
                    if _job_identity(rj) not in local_keys and _recently_created(rj):
                        local_jobs.setdefault(dkey, []).append(rj)
                        local_keys.add(_job_identity(rj))
            _protect_worker_fields(payload_obj, fresh_obj)
        try:
            gh_put(DATA_FILE, payload_obj, sha=fresh_sha)
            return
        except Exception as e:
            if attempt == 2:
                raise e
            import time; time.sleep(0.5)

def save_jobs(jobs_dict, _sha_hint=None):
    save_data(jobs_dict, mcs, site_visits, svr_confirmed, checklist, live_hire, materials, materials_totals, _sha_hint)

# ── Date helpers ──────────────────────────────────────────────────────────────
def get_monday(d): return d - timedelta(days=d.weekday())
def fmt_key(d):    return d.strftime("%Y-%m-%d")
def week_num(d):   return d.isocalendar()[1]

# ── Bank holidays (England) ───────────────────────────────────────────────────
@st.cache_data(ttl=86400)
def get_bank_holidays():
    """Fetch England bank holidays from gov.uk API. Cache for 24 hours."""
    try:
        r = requests.get(
            "https://www.gov.uk/bank-holidays.json",
            timeout=5
        )
        r.raise_for_status()
        data = r.json()
        events = data.get("england-and-wales", {}).get("events", [])
        return {e["date"]: e["title"] for e in events}
    except Exception:
        # Fallback: hardcoded 2025-2026 England bank holidays
        return {
            "2025-01-01": "New Year's Day",
            "2025-04-18": "Good Friday",
            "2025-04-21": "Easter Monday",
            "2025-05-05": "Early May Bank Holiday",
            "2025-05-26": "Spring Bank Holiday",
            "2025-08-25": "Summer Bank Holiday",
            "2025-12-25": "Christmas Day",
            "2025-12-26": "Boxing Day",
            "2026-01-01": "New Year's Day",
            "2026-04-03": "Good Friday",
            "2026-04-06": "Easter Monday",
            "2026-05-04": "Early May Bank Holiday",
            "2026-05-25": "Spring Bank Holiday",
            "2026-08-31": "Summer Bank Holiday",
            "2026-12-25": "Christmas Day",
            "2026-12-28": "Boxing Day (substitute)",
        }

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in [("week_offset", 0), ("n_weeks", 4),
             ("modal_date", None), ("modal_edit_idx", None),
             ("expand_date", None), ("expand_idx", None),
             ("day_view_date", None),
             ("move_from_date", None), ("move_job_idx", None),
             ("svr_modal_date", None), ("svr_modal_idx", None),
             ("msv_from_date", None), ("msv_idx", None),
             ("mat_add", False), ("mat_view_id", None),
             ("query_date", None), ("query_idx", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

jobs, mcs, site_visits, svr_confirmed, checklist, live_hire, materials, materials_totals, queries, sha = load_data()
bank_holidays = get_bank_holidays()

# Auto-expire finished materials older than 24h: legacy pod_received
# lines, plus requests where EVERY line is ticked Delivered (the last
# delivery stamp starts the clock).
_now = datetime.now()
_mat_changed = False

def _mat_boot_stamp(raw):
    try:
        return datetime.strptime(raw or "", "%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return None

for mid, req in list(materials.items()):
    if req.get("status") == "pod_received" and req.get("pod_received_at"):
        _pod = _mat_boot_stamp(req["pod_received_at"])
        if _pod and (_now - _pod).total_seconds() > 86400:
            del materials[mid]
            _mat_changed = True
_boot_groups = {}
for mid, req in materials.items():
    _k = (req.get("request_id")
          or f"{req.get('requester','')}|{req.get('created_at','')}")
    _boot_groups.setdefault(_k, []).append(mid)
for _k, _mids in _boot_groups.items():
    _recs = [materials[m] for m in _mids]
    if _recs and all(r.get("delivered") for r in _recs):
        _stamps = [_mat_boot_stamp(r.get("delivered_at")) for r in _recs]
        if all(_stamps) and \
                (_now - max(_stamps)).total_seconds() > 86400:
            for m in _mids:
                del materials[m]
            _mat_changed = True
if _mat_changed:
    save_data(jobs, mcs, site_visits, svr_confirmed, checklist, live_hire, materials, materials_totals)

import uuid as _uuid
import hashlib as _hashlib

def open_dialog(**kwargs):
    """Set dialog state with a unique token so it only opens once per click."""
    token = _uuid.uuid4().hex[:8]
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.session_state["any_dialog_open"] = True
    _token_map = {
        "day_view_date":  "dv_token",
        "modal_date":     "modal_token",
        "svr_modal_date": "svr_token",
        "move_from_date": "move_token",
        "msv_from_date":  "msv_token",
        "expand_date":    "expand_token",
        "query_date":     "query_token",
    }
    for k in kwargs:
        if k in _token_map:
            st.session_state[_token_map[k]] = token
            break

def close_dialog(**kwargs):
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.session_state["any_dialog_open"] = False

# ── Job queries (yard asks, office answers) ───────────────────────────────────
# Queries live in their own store keyed by a random id. Each one records the
# day and the job it was raised against, plus enough of the job's identity
# (customer + contract) that it still reads correctly if jobs are reordered
# or moved. Status runs open -> answered -> closed.
#   open     the yard has asked something and nobody has replied. The day
#            card pulses red while any query on that day is open.
#   answered the office has replied. The pulse stops, the day shows a
#            green reply flag and the answer is on the job.
#   closed   the yard has seen the answer and cleared it away.
QUERY_OFFICE = ["Ewa", "Klaudia", "Chloe", "Nick", "Chris", "Mitch", "Peter",
                "Nathan"]
# Everyone on the weekly clocking report, plus Chris. Both Stephens are
# spelled out so the yard can tell them apart.
QUERY_YARD = ["Alex", "Baz", "Carl", "Chris", "Claude", "Cliff", "Dan",
              "Jim", "Josh", "Keaton", "Mark", "Matt", "Mel", "Mitch",
              "Rich", "Ste Barlow", "Steve Taylor"]

def _job_query_ref(job):
    """Stable-ish label for the job a query was raised against."""
    cn = str(job.get("contract_number") or "").strip()
    return {
        "customer": job.get("customer", ""),
        "contract": "" if cn in ("", "00000") else cn,
        "job_type": job.get("type", ""),
        "postcode": job.get("postcode", ""),
    }

def _queries_for_job(date_key, job_idx):
    """Queries raised against one job, oldest first, excluding closed ones."""
    out = []
    for qid, q in queries.items():
        if q.get("date") != date_key or q.get("status") == "closed":
            continue
        if int(q.get("job_idx", -1)) != int(job_idx):
            continue
        out.append((qid, q))
    out.sort(key=lambda x: x[1].get("raised_at", ""))
    return out

def _day_query_counts(date_key):
    """(open, answered) query counts for a day, ignoring closed ones."""
    n_open = n_ans = 0
    for q in queries.values():
        if q.get("date") != date_key:
            continue
        if q.get("status") == "open":
            n_open += 1
        elif q.get("status") == "answered":
            n_ans += 1
    return n_open, n_ans

def _save_all():
    save_data(jobs, mcs, site_visits, svr_confirmed, checklist,
              live_hire, materials, materials_totals)

# ── Checked By ────────────────────────────────────────────────────────────────
# The yard signs their name against a job once they have been over it. Stored
# on the existing checklist so nothing new has to be threaded through save.
# Same people as can raise a query: the clocking report plus Chris.
CHECKED_BY_PEOPLE = QUERY_YARD
CHECKED_BY_NONE   = "— Not checked —"

def _checked_by_key(date_key, job_idx):
    return f"checkedby_{date_key}_{job_idx}"

def _checked_by(date_key, job_idx):
    """Name of whoever checked this job over, or '' if nobody has."""
    return str(checklist.get(_checked_by_key(date_key, job_idx), "") or "")

def _query_delete_button(qid):
    """Delete a query outright. Two clicks, so nothing goes by accident."""
    confirm_key = f"qdel_confirm_{qid}"
    if st.session_state.get(confirm_key):
        st.warning("Delete this query for good?")
        dc1, dc2 = st.columns(2)
        with dc1:
            if st.button("🗑️ Yes, delete", key=f"qdel_yes_{qid}",
                         type="primary", use_container_width=True):
                queries.pop(qid, None)
                st.session_state[confirm_key] = False
                _save_all()
                st.rerun()
        with dc2:
            if st.button("Keep it", key=f"qdel_no_{qid}",
                         use_container_width=True):
                st.session_state[confirm_key] = False
                st.rerun()
    else:
        if st.button("🗑️ Delete query", key=f"qdel_{qid}",
                     use_container_width=True):
            st.session_state[confirm_key] = True
            st.rerun()

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{{font-family:'Figtree',Calibri,sans-serif;color:{K_GREY};}}
.main .block-container{{padding-top:0.75rem;padding-bottom:2rem;max-width:100%;}}


/* ── Yard Board, 02/11/2026 ── */
::selection{{background:#cfe8d7;color:#10231a;}}
.yb-bar{{background:{K_GREEN};color:#fff;display:flex;align-items:center;gap:14px;
        padding:12px 18px;border-radius:10px;margin:0 0 10px;}}
.yb-bar-title{{font-size:18px;font-weight:600;color:#fff;}}
.yb-range{{font-size:15px;font-weight:700;color:#1f2125;white-space:nowrap;}}
.yb-week{{margin:16px 0 8px;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 18px;}}
.yb-week h3{{margin:0;padding:0;font-size:19px;font-weight:700;color:#1f2125;}}
.yb-week p{{margin:0;font-size:14px;color:#4f535b;display:flex;flex-wrap:wrap;gap:4px 14px;}}
.yb-week b{{font-weight:700;}} .yb-week b.g{{color:#0a6a30;}} .yb-week b.r{{color:#a61b1b;}} .yb-week b.b{{color:#1d5fae;}}
.yb-day{{background:#f9faf8;border:1px solid #e1e5e1;border-radius:10px;margin-bottom:6px;}}
.yb-day.is-today{{background:#e9f4ec;border-color:#a9d3b6;}}
.yb-day.is-weekend{{background:#eef0ed;}}
.yb-day.is-bh{{background:#fffbea;border-color:#e6c200;}}
.yb-day.has-query{{border-color:#e7a59c;}}
.yb-day-head{{padding:9px 11px 8px;display:flex;flex-direction:column;gap:4px;}}
.yb-day-top{{display:flex;align-items:center;justify-content:space-between;gap:8px;}}
.yb-day-name{{font-size:15px;font-weight:700;color:#1f2125;}}
.yb-day-name span{{font-weight:500;color:#4f535b;}}
.yb-today{{font-size:12px;font-weight:700;color:#0a6a30;}}
.yb-qcount{{min-width:20px;height:20px;padding:0 6px;box-sizing:border-box;border-radius:10px;
           background:#b42318;color:#fff;font-size:12px;font-weight:800;display:inline-flex;
           align-items:center;justify-content:center;margin-left:6px;}}
.yb-counts{{display:flex;gap:10px;flex-wrap:wrap;font-size:13px;color:#4f535b;}}
.yb-counts span{{display:inline-flex;align-items:center;gap:3px;}}
.yb-bh{{font-size:12px;font-weight:700;color:#7a5c00;}}
.yb-dailys{{font-size:12px;font-weight:700;color:#0a6a30;}}
.yb-sv{{font-size:12px;font-weight:700;color:{K_PURPLE_DARK};}}
.yb-job{{background:#fff;border:1px solid #dfe3df;border-radius:8px;padding:8px 9px;
        display:flex;flex-direction:column;gap:3px;font-size:13px;line-height:1.3;color:#1f2125;
        box-shadow:0 1px 2px rgba(16,35,26,.06);transition:border-color .15s,background .15s;}}
.yb-job-top{{display:flex;align-items:center;gap:5px;font-size:12px;font-weight:700;}}
.yb-time{{margin-left:auto;display:inline-flex;align-items:center;gap:3px;color:#4f535b;font-weight:600;}}
.yb-cust{{font-size:14px;font-weight:700;}}
.yb-units{{color:#3c3f45;}}
.yb-meta{{font-size:12px;color:#4f535b;display:flex;flex-wrap:wrap;gap:4px 8px;align-items:center;}}
.yb-tag{{font-weight:700;color:#4f535b;}}
.yb-state{{display:flex;flex-wrap:wrap;gap:6px;font-size:12px;font-weight:600;}}
.yb-ok{{color:#0a6a30;display:inline-flex;align-items:center;gap:3px;}}
.yb-not{{color:#6b5a00;}}
.yb-qopen{{color:#fff;background:#b42318;border-radius:4px;padding:0 6px;}}
.yb-qans{{color:#1d4f91;}}
.yb-empty{{font-size:13px;color:#5d6168;padding:4px 4px 8px;}}
/* the whole job row is the button: the real button is stretched over it */
[class*="st-key-ybjob_"]{{position:relative;gap:0 !important;margin-bottom:6px;}}
[class*="st-key-ybjob_"] > div:has([data-testid="stButton"]){{position:absolute !important;inset:0;margin:0;z-index:2;}}
[class*="st-key-ybjob_"] [data-testid="stButton"]{{position:absolute;inset:0;margin:0;}}
[class*="st-key-ybjob_"] [data-testid="stButton"] > div, [class*="st-key-ybjob_"] [data-testid="stButton"] button{{width:100% !important;height:100% !important;}}
[class*="st-key-ybjob_"] [data-testid="stButton"] button{{opacity:0;cursor:pointer;}}
[class*="st-key-ybjob_"]:hover .yb-job{{border-color:#9fb8a8;background:#fbfdfb;}}
[class*="st-key-ybjob_"]:focus-within .yb-job{{outline:2px solid {K_GREEN};outline-offset:2px;}}
[class*="st-key-ybadd_"] button{{border:1px dashed #b9c2bb !important;background:transparent !important;
        color:#3c3f45 !important;font-weight:600 !important;}}
[class*="st-key-ybadd_"] button:hover{{background:#eef2ef !important;}}
[class*="st-key-ybband_"] button{{min-height:240px;background:#e9ecea !important;border:1px solid #dfe3df !important;
        border-radius:10px !important;padding:8px 0 !important;color:#3c3f45 !important;}}
[class*="st-key-ybband_"] button p{{writing-mode:vertical-rl;font-size:12px !important;font-weight:700;letter-spacing:.04em;}}
[class*="st-key-ybband_"] button:hover{{background:#dde3df !important;color:#1f2125 !important;}}
.yb-side-head{{font-size:15px;font-weight:700;color:#1f2125;display:flex;align-items:center;margin:4px 0 8px;}}
.yb-q{{background:#fdf0ee;border:1px solid #f1c3bc;border-radius:8px;padding:9px 10px;margin-bottom:4px;}}
.yb-q-top{{font-size:12px;font-weight:700;color:#8f1c13;}}
.yb-q-cust{{font-size:14px;font-weight:700;color:#1f2125;}}
.yb-q-text{{font-size:14px;font-weight:600;color:#1f2125;line-height:1.4;margin-top:2px;}}

/* Header */
.ks-header{{display:flex;align-items:center;gap:12px;padding:10px 0 12px;
            border-bottom:2px solid {K_GREEN};margin-bottom:1rem;}}
.ks-title{{font-size:20px;font-weight:800;color:{K_GREEN};letter-spacing:-.3px;}}
.ks-sub{{font-size:12px;color:{K_GREY};opacity:.6;margin-left:auto;}}

/* Day cards */
.day-card{{border:1px solid {K_LGREY};border-radius:10px;overflow:hidden;
           min-height:130px;background:{K_WHITE};margin:2px;}}
.day-card.is-today{{border-color:{K_GREEN};border-width:2px;}}
.day-card.is-weekend{{background:#fafafa;}}
.day-head{{padding:7px 9px 5px;border-bottom:1px solid {K_LGREY};}}
.day-name{{font-size:10px;font-weight:700;color:{K_GREY};opacity:.5;
           text-transform:uppercase;letter-spacing:.07em;}}
.day-date{{font-size:17px;font-weight:800;color:{K_GREY};}}
.day-date.is-today{{color:{K_GREEN};}}
.day-body{{padding:5px;}}

/* Materials Request panel */
.mat-panel {{
  border: 1px solid {K_LGREY}; border-radius: 10px; overflow: hidden;
  background: #fafafa; margin: 2px; min-height: 170px;
}}
.mat-panel-head {{
  padding: 7px 9px 5px; border-bottom: 1px solid {K_LGREY};
  background: #f0f0f0;
}}
.mat-panel-title {{
  font-size: 10px; font-weight: 700; color: {K_GREY}; opacity: .5;
  text-transform: uppercase; letter-spacing: .07em;
}}
.mat-panel-label {{
  font-size: 13px; font-weight: 800; color: {K_GREY};
}}
.mat-pill {{
  border-radius: 6px; padding: 4px 8px; margin-bottom: 3px;
  font-size: 11px; line-height: 1.4; cursor: pointer;
}}
.mat-pill.pending  {{ background: #fdecea; color: #7b1a1a; }}
.mat-pill.ordered  {{ background: #fff9e6; color: #7a5c00; }}
.mat-pill.pod      {{ background: {K_GREEN_PALE}; color: {K_GREEN_DARK}; }}

/* Materials pill buttons inside scroll container */
.mat-scroll button {{
  text-align: left !important;
  justify-content: flex-start !important;
  border-radius: 6px !important;
  padding: 5px 9px !important;
  margin-bottom: 3px !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  border: none !important;
  min-height: 0 !important;
  height: auto !important;
  line-height: 1.3 !important;
}}
.mat-scroll button p {{ font-size: 11px !important; font-weight: 700 !important; }}
.day-sum-pill{{display:flex;align-items:center;gap:5px;padding:3px 5px;
               border-radius:5px;margin-bottom:2px;font-size:11px;font-weight:600;
               border:2px solid transparent;}}
/* Every job of this type has been checked over by the yard */
@keyframes checked-glow {{
  0%, 100% {{ box-shadow: 0 0 3px 0 rgba(13,130,59,.35); }}
  50%       {{ box-shadow: 0 0 9px 2px rgba(13,130,59,.60); }}
}}
.day-sum-pill.is-checked{{border-color:{K_GREEN} !important;
               animation:checked-glow 2s ease-in-out infinite;}}
.day-sum-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;}}
.day-sum-label{{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.day-sum-haul{{font-size:9px;opacity:.65;margin-left:2px;}}
.day-empty{{font-size:10px;color:{K_GREY};opacity:.3;padding:4px 5px;font-style:italic;}}

/* Day click button — invisible, covers body */
.ks-day-btn button {{
  background: transparent !important;
  border: none !important;
  color: {K_GREEN} !important;
  font-size: 10px !important;
  font-weight: 600 !important;
  width: 100% !important;
  padding: 2px 4px !important;
  border-radius: 4px !important;
  opacity: 0.6;
}}
.ks-day-btn button:hover {{
  background: {K_GREEN_PALE} !important;
  opacity: 1;
}}

/* Job chips */
.jchip{{border-radius:6px;padding:5px 8px;margin-bottom:3px;
        font-size:11.5px;line-height:1.4;cursor:pointer;}}
.jchip:hover{{filter:brightness(.96);}}
.jchip-name{{font-weight:700;display:block;font-size:12px;}}
.jchip-sub{{font-size:10px;opacity:.75;display:block;}}
.jchip-units{{font-size:10px;opacity:.6;display:block;margin-top:1px;}}
.jchip-idtag{{display:inline-block;font-size:9.5px;font-weight:700;
              background:rgba(0,0,0,.08);border-radius:3px;padding:1px 5px;margin-top:2px;}}
.jchip-ts{{display:block;font-size:9px;opacity:.55;margin-top:2px;font-style:italic;}}

/* Add buttons — white background, green text/border */
.ks-add-btn button {{
  background-color: white !important;
  color: {K_GREEN} !important;
  border: 1.5px solid {K_GREEN} !important;
  font-weight: 700 !important;
  border-radius: 6px !important;
}}
.ks-add-btn button:hover {{
  background-color: {K_GREEN_PALE} !important;
}}

/* Chip button wrapper — hides the button, chip is the visual trigger */
.ks-chip-btn {{ margin-bottom: 4px; }}
.ks-chip-btn button {{
  background: transparent !important;
  border: none !important;
  color: {K_GREEN} !important;
  font-size: 10px !important;
  font-weight: 600 !important;
  padding: 1px 4px !important;
  margin-top: -2px !important;
  border-radius: 4px !important;
  height: auto !important;
  min-height: unset !important;
  opacity: 0.7;
}}
.ks-chip-btn button:hover {{
  background: {K_GREEN_PALE} !important;
  opacity: 1;
}}

/* Week bar */
.wk-bar{{background:{K_GREEN_PALE};border:1px solid #c3dfc9;border-radius:8px;
         padding:6px 10px;margin-bottom:6px;font-size:11px;color:{K_GREEN_DARK};}}
.wk-bar-title{{font-weight:700;font-size:11px;margin-bottom:3px;}}
.wk-unit-row{{display:flex;flex-wrap:wrap;gap:4px;}}
.wku{{background:{K_GREEN};color:white;border-radius:4px;padding:2px 7px;
      font-size:10.5px;font-weight:600;}}
.wku.off{{background:#c05500;}}

/* Pill summary */
.pill{{display:inline-block;border-radius:20px;padding:4px 12px;
       font-size:12px;font-weight:600;margin-right:5px;margin-bottom:5px;}}

/* Snapshot */
.snap-outer{{font-family:'Figtree',Calibri,sans-serif;}}
.snap-header{{background:{K_GREEN};color:white;padding:14px 20px;border-radius:10px 10px 0 0;}}
.snap-title{{font-size:18px;font-weight:800;letter-spacing:-.2px;}}
.snap-period{{font-size:12px;opacity:.8;margin-top:2px;}}
.snap-grid{{display:grid;grid-template-columns:repeat(7,1fr);
            border:1px solid {K_LGREY};border-top:none;}}
.snap-dh{{background:#f5f5f5;padding:6px 8px;border-right:1px solid {K_LGREY};
          border-bottom:1px solid {K_LGREY};}}
.snap-dname{{font-size:9px;font-weight:700;text-transform:uppercase;
             color:{K_GREY};opacity:.5;letter-spacing:.06em;}}
.snap-ddate{{font-size:14px;font-weight:800;color:{K_GREY};}}
.snap-ddate.snap-today{{color:{K_GREEN};}}
.snap-body{{padding:5px;border-right:1px solid {K_LGREY};
            border-bottom:1px solid {K_LGREY};min-height:80px;vertical-align:top;}}
.snap-chip{{border-radius:4px;padding:3px 6px;margin-bottom:2px;font-size:10px;line-height:1.3;}}
.snap-name{{font-weight:700;display:block;}}
.snap-sub{{font-size:9px;opacity:.7;}}
.snap-footer{{background:#f9f9f9;padding:8px 16px;border:1px solid {K_LGREY};
              border-top:none;border-radius:0 0 10px 10px;
              font-size:10px;color:{K_GREY};opacity:.6;text-align:right;}}

/* Day Complete animation */
@keyframes day-complete {{
  0%   {{ transform: scale(0.8); opacity: 0; }}
  50%  {{ transform: scale(1.08); opacity: 1; }}
  70%  {{ transform: scale(0.97); }}
  100% {{ transform: scale(1); opacity: 1; }}
}}
@keyframes confetti-spin {{
  0%   {{ transform: rotate(0deg) translateY(0);   opacity: 1; }}
  100% {{ transform: rotate(720deg) translateY(-20px); opacity: 0; }}
}}
.day-complete-banner {{
  animation: day-complete 0.6s cubic-bezier(.34,1.56,.64,1) forwards;
  background: linear-gradient(135deg, {K_GREEN} 0%, {K_GREEN_DARK} 100%);
  color: white; border-radius: 12px; padding: 16px 20px;
  text-align: center; margin: 1rem 0;
}}
.day-complete-title {{
  font-size: 20px; font-weight: 800; letter-spacing: -.3px; margin-bottom: 2px;
}}
.day-complete-sub {{
  font-size: 13px; opacity: .85;
}}
.day-card.is-bh {{ background: #fffbea !important; border-color: #e6c200 !important; }}
.bh-label {{ font-size: 9px; font-weight: 700; color: #7a6000;
             background: #fff3b0; border-radius: 3px; padding: 1px 5px;
             display: inline-block; margin-top: 2px; }}

/* Day card fully processed — gold glow */
@keyframes glow-pulse {{
  0%, 100% {{ box-shadow: 0 0 0 2px #f0b429, 0 0 10px 2px rgba(240,180,41,.25); }}
  50%       {{ box-shadow: 0 0 0 2px #f0b429, 0 0 18px 5px rgba(240,180,41,.4); }}
}}
.day-card.is-complete {{
  border-color: #f0b429 !important;
  border-width: 2px !important;
  animation: glow-pulse 2.5s ease-in-out infinite;
}}

/* Day card has a LIVE yard query — red glow, beats every other state */
@keyframes query-pulse {{
  0%, 100% {{ box-shadow: 0 0 0 2px #c0392b, 0 0 8px 2px rgba(192,57,43,.30); }}
  50%       {{ box-shadow: 0 0 0 3px #e74c3c, 0 0 20px 7px rgba(192,57,43,.55); }}
}}
.day-card.has-query {{
  border-color: #c0392b !important;
  border-width: 2px !important;
  background: #fffafa;
  animation: query-pulse 1.3s ease-in-out infinite;
}}
.day-query-flag {{
  font-size: 9px; font-weight: 800; color: #7b1a1a;
  background: #fdecea; border-radius: 3px; padding: 1px 5px;
  display: inline-block; margin-top: 1px;
}}
.day-answer-flag {{
  font-size: 9px; font-weight: 800; color: {K_GREEN_DARK};
  background: {K_GREEN_PALE}; border-radius: 3px; padding: 1px 5px;
  display: inline-block; margin-top: 1px;
}}

/* MCS tick sparkle animation */
@keyframes mcs-sparkle {{
  0%   {{ transform: scale(1);   opacity: 1; }}
  20%  {{ transform: scale(1.35); opacity: 1; }}
  40%  {{ transform: scale(0.9);  opacity: 1; }}
  60%  {{ transform: scale(1.15); opacity: 1; }}
  100% {{ transform: scale(1);   opacity: 1; }}
}}
@keyframes mcs-stars {{
  0%   {{ opacity: 0; transform: scale(0) rotate(0deg); }}
  50%  {{ opacity: 1; transform: scale(1.4) rotate(180deg); }}
  100% {{ opacity: 0; transform: scale(0) rotate(360deg); }}
}}
.mcs-done {{
  animation: mcs-sparkle 0.5s ease;
  display: inline-flex; align-items: center; gap: 5px;
  background: {K_GREEN_PALE}; color: {K_GREEN_DARK};
  border-radius: 6px; padding: 4px 10px;
  font-size: 12px; font-weight: 700;
}}
.mcs-done-red {{
  animation: mcs-sparkle 0.5s ease;
  display: inline-flex; align-items: center; gap: 5px;
  background: #fdecea; color: #7b1a1a;
  border-radius: 6px; padding: 4px 10px;
  font-size: 12px; font-weight: 700;
}}
</style>
""", unsafe_allow_html=True)

# ── DAY VIEW DIALOG (all jobs for a day) ─────────────────────────────────────
@st.dialog("Day Schedule", width="large")
def day_view_dialog(date_key):
    day_label = datetime.strptime(date_key, "%Y-%m-%d").strftime("%A %-d %B %Y")
    bh = bank_holidays.get(date_key, "")
    header_extra = f"  ·  🏴󠁧󠁢󠁥󠁮󠁧󠁿 {bh}" if bh else ""
    st.markdown(
        f"<div style='font-size:14px;font-weight:700;color:{K_GREEN};"
        f"margin-bottom:1rem;'>📅 {day_label}{header_extra}</div>",
        unsafe_allow_html=True)

    day_jobs = jobs.get(date_key, [])

    if not day_jobs:
        st.info("No jobs booked for this day.")
    else:
        for ji, job in enumerate(day_jobs):
            bg, fg, _ = TYPE_STYLE[job["type"]]
            haulage    = job.get("haulage", "None")
            border_col = K_GREEN if haulage == "Internal Haulage" else ("#c0392b" if haulage == "External Haulage" else "transparent")

            units_html = ""
            if job.get("units"):
                unit_items = "".join(
                    f'<span style="display:inline-block;background:{bg};color:{fg};'
                    f'border-radius:4px;padding:2px 8px;font-size:11px;font-weight:600;'
                    f'margin:2px 2px 0 0;">{u} ×{q}</span>'
                    for u, q in job["units"].items() if q
                )
                units_html = f"<div style='margin-top:6px;'>{unit_items}</div>"

            # AV config breakdown
            av_cfg_html = ""
            av_cfgs = job.get("av_configs", {})
            if av_cfgs:
                cfg_lines = []
                for av_unit, cfgs in av_cfgs.items():
                    if cfgs:
                        parts = ", ".join(f"{c} ×{n}" for c, n in cfgs.items())
                        cfg_lines.append(
                            f'<div style="font-size:10.5px;opacity:.75;margin-top:3px;">'
                            f'<b>{av_unit}:</b> {parts}</div>'
                        )
                if cfg_lines:
                    av_cfg_html = (
                        f'<div style="margin-top:6px;padding-top:6px;'
                        f'border-top:1px solid rgba(0,0,0,.08);">'
                        + "".join(cfg_lines) + "</div>"
                    )

            tags = f'<span style="background:rgba(0,0,0,.09);border-radius:4px;padding:2px 8px;font-size:11px;font-weight:700;">{job["type"]}</span>'
            # Site Move sub-type
            if job.get("site_move_type"):
                sm_icon = "🔄" if job["site_move_type"] == "Movement on Same Site" else "🚚"
                tags += (f' <span style="background:#eef2ff;color:#2d3a8c;border-radius:4px;'
                         f'padding:2px 8px;font-size:11px;font-weight:700;">'
                         f'{sm_icon} {job["site_move_type"]}</span>')
            if job.get("install_dismantle"):
                tags += f' <span style="background:{K_GREEN};color:white;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:700;">I/D</span>'
            if haulage != "None":
                haul_bg   = K_GREEN_PALE if haulage == "Internal Haulage" else "#fdecea"
                haul_fg   = K_GREEN_DARK if haulage == "Internal Haulage" else "#7b1a1a"
                haul_icon = "🚛" if haulage == "Internal Haulage" else "🚚"
                haul_who  = job.get("haulage_who", "")
                haul_label = f"{haul_icon} {haulage}" + (f" — {haul_who}" if haul_who else "")
                tags += (f' <span style="background:{haul_bg};color:{haul_fg};border-radius:4px;'
                         f'padding:2px 8px;font-size:11px;font-weight:700;">{haul_label}</span>')
            livery = job.get("livery", "Standard Livery")
            if livery == "Customer Livery — Specify":
                livery_note = job.get("livery_note", "")
                livery_label = f"🎨 {livery_note}" if livery_note else "🎨 Customer Livery"
                tags += (f' <span style="background:#f3e8ff;color:#5b21b6;border-radius:4px;'
                         f'padding:2px 8px;font-size:11px;font-weight:700;">{livery_label}</span>')
            else:
                tags += (f' <span style="background:#f0f0f0;color:{K_GREY};border-radius:4px;'
                         f'padding:2px 8px;font-size:11px;font-weight:700;">🏭 Standard Livery</span>')

            ts_line = ""
            if job.get("added_by") or job.get("timestamp"):
                ts_line = (f'<div style="font-size:10px;opacity:.5;margin-top:6px;">'
                           f'🕐 {job.get("added_by","")} · {job.get("timestamp","")}</div>')
            if job.get("edited_at"):
                ts_line += (f'<div style="font-size:10px;opacity:.5;">'
                            f'✏️ {job.get("edited_by","")} · {job["edited_at"]}</div>')

            job_type_val = job["type"]

            # Per-job fulfilment checks. On Hire no longer carries POD /
            # Contract / Picked on MCS - those were retired at Nathan's
            # request, so only Off Hire has per-job checks now.
            JOB_CHECK_LABELS = {
                "Off Hire": [("poc", "📎 POC Attached?"), ("returns",  "🔄 Lines Returned?")],
            }
            job_checks   = JOB_CHECK_LABELS.get(job_type_val, [])
            base_ck      = f"job_{date_key}_{ji}"
            checks_done  = bool(job_checks) and all(
                checklist.get(f"{base_ck}_{ck}", False) for ck, _ in job_checks
            )
            all_job_done = checks_done
            checked_by   = _checked_by(date_key, ji)
            # Gold when every check is done, green when the yard has signed
            # it off, plain otherwise
            if all_job_done:
                card_border = ("border:2px solid #f0b429;"
                               "box-shadow:0 0 10px rgba(240,180,41,.35);")
            elif checked_by:
                card_border = (f"border:2px solid {K_GREEN};"
                               "box-shadow:0 0 10px rgba(13,130,59,.35);")
            else:
                card_border = f"border-left:5px solid {border_col};"
            done_badge = (
                ' <span style="font-size:10px;font-weight:700;background:#f0b429;'
                'color:#7a5c00;border-radius:3px;padding:1px 6px;margin-left:4px;">✨ Done</span>'
                if all_job_done else ""
            )
            if checked_by:
                done_badge += (
                    f' <span style="font-size:10px;font-weight:700;'
                    f'background:{K_GREEN};color:white;border-radius:3px;'
                    f'padding:1px 6px;margin-left:4px;">✅ Checked by '
                    f'{checked_by}</span>')

            # Queries raised against this job
            job_qs      = _queries_for_job(date_key, ji)
            job_q_open  = [q for _, q in job_qs if q.get("status") == "open"]
            job_q_ans   = [q for _, q in job_qs if q.get("status") == "answered"]
            if job_q_open:
                q_btn_label, q_btn_help = "❗", "Open query on this job"
            elif job_q_ans:
                q_btn_label, q_btn_help = "💬", "The office has answered"
            else:
                q_btn_label, q_btn_help = "❓", "Query a detail on this job"

            rc1, rc2, rc3, rc4 = st.columns([5, 1, 1, 1])
            with rc1:
                # Query banner — live questions and answers, on the job card
                q_html = ""
                for _qid, q in job_qs:
                    if q.get("status") == "open":
                        q_html += (
                            f'<div style="margin-top:6px;padding:6px 8px;'
                            f'background:#fdecea;border-left:3px solid #c0392b;'
                            f'border-radius:5px;font-size:11px;color:#7b1a1a;">'
                            f'<b>❗ Query from {q.get("raised_by","")}</b> '
                            f'<span style="opacity:.6;">{q.get("raised_at","")}</span>'
                            f'<div style="margin-top:2px;">{q.get("question","")}</div>'
                            f'</div>')
                    else:
                        q_html += (
                            f'<div style="margin-top:6px;padding:6px 8px;'
                            f'background:{K_GREEN_PALE};border-left:3px solid {K_GREEN};'
                            f'border-radius:5px;font-size:11px;color:{K_GREEN_DARK};">'
                            f'<div style="opacity:.75;">❓ {q.get("raised_by","")}: '
                            f'{q.get("question","")}</div>'
                            f'<div style="margin-top:3px;"><b>💬 '
                            f'{q.get("answered_by","")}</b> '
                            f'<span style="opacity:.6;">{q.get("answered_at","")}</span>'
                            f'<br>{q.get("answer","")}</div>'
                            f'</div>')

                contract_num = job.get("contract_number", "")
                contract_html = ""
                if contract_num and contract_num != "00000":
                    contract_html = (
                        f'<span style="font-size:14px;font-weight:500;opacity:.6;'
                        f'margin-left:8px;background:rgba(0,0,0,.07);border-radius:4px;'
                        f'padding:1px 7px;">{contract_num}</span>'
                    )
                # Notes
                notes_html = ""
                if job.get("notes"):
                    notes_by  = job.get("notes_edited_by", "")
                    notes_at  = job.get("notes_edited_at", "")
                    notes_stamp = (f'<span style="font-size:9px;opacity:.5;margin-left:6px;">'
                                   f'✏️ {notes_by} · {notes_at}</span>' if notes_by else "")
                    notes_html = (
                        f'<div style="margin-top:6px;padding:6px 8px;'
                        f'background:rgba(0,0,0,.05);border-radius:5px;font-size:11px;">'
                        f'📝 {job["notes"]}{notes_stamp}</div>'
                    )

                st.markdown(f"""
                <div style="background:{bg};color:{fg};border-radius:10px;
                            {card_border}padding:12px 14px;margin-bottom:4px;">
                  <div style="font-size:17px;font-weight:800;margin-bottom:2px;">
                    {job.get("customer","")}{contract_html}{done_badge}</div>
                  <div style="font-size:12px;opacity:.65;margin-bottom:6px;">{job.get("postcode","")}</div>
                  <div>{tags}</div>
                  {units_html}
                  {av_cfg_html}
                  {notes_html}
                  {q_html}
                  {ts_line}
                </div>
                """, unsafe_allow_html=True)

                # ── Per-job checks ──────────────────────────────────────────
                if job_checks:
                    st.markdown(
                        "<div style='margin-top:2px;margin-bottom:4px;'></div>",
                        unsafe_allow_html=True)
                    jc_cols = st.columns(len(job_checks))
                    job_ck_changed = False
                    for ci_jc, (ck, label) in enumerate(job_checks):
                        with jc_cols[ci_jc]:
                            key    = f"{base_ck}_{ck}"
                            cur    = checklist.get(key, False)
                            newval = st.checkbox(label, value=cur, key=f"jchk_{key}")
                            if newval != cur:
                                checklist[key] = newval
                                job_ck_changed = True
                    if job_ck_changed:
                        save_data(jobs, mcs, site_visits, svr_confirmed, checklist, live_hire, materials, materials_totals)
                        st.rerun()

            with rc2:
                if st.button("✏️", key=f"dv_edit_{date_key}_{ji}",
                             use_container_width=True, help="Edit this job"):
                    st.session_state["modal_date"]      = date_key
                    st.session_state["modal_edit_idx"]  = ji
                    st.session_state["modal_token"]     = _uuid.uuid4().hex[:8]
                    st.session_state["any_dialog_open"] = True
                    st.session_state["day_view_date"]   = None
                    st.rerun()
            with rc3:
                if st.button("📅", key=f"dv_move_{date_key}_{ji}",
                             use_container_width=True, help="Move to another day"):
                    st.session_state["move_from_date"] = date_key
                    st.session_state["move_token"] = _uuid.uuid4().hex[:8]
                    st.session_state["any_dialog_open"] = True
                    st.session_state["move_job_idx"]   = ji
                    st.session_state["day_view_date"]  = None
                    st.rerun()
            with rc4:
                if st.button(q_btn_label, key=f"dv_query_{date_key}_{ji}",
                             use_container_width=True, help=q_btn_help):
                    st.session_state["query_date"]      = date_key
                    st.session_state["query_idx"]       = ji
                    st.session_state["query_token"]     = _uuid.uuid4().hex[:8]
                    st.session_state["any_dialog_open"] = True
                    st.session_state["day_view_date"]   = None
                    st.rerun()

            # ── Checked By — sits under the edit / move / query buttons ──
            _cb_pad, _cb_col = st.columns([5, 3])
            with _cb_col:
                cb_opts = [CHECKED_BY_NONE] + CHECKED_BY_PEOPLE
                cb_cur  = checked_by if checked_by in CHECKED_BY_PEOPLE else CHECKED_BY_NONE
                cb_new  = st.selectbox(
                    "Checked By", cb_opts, index=cb_opts.index(cb_cur),
                    key=f"dv_checkedby_{date_key}_{ji}",
                    help="Who has been over this job")
                if cb_new != cb_cur:
                    ck_key = _checked_by_key(date_key, ji)
                    if cb_new == CHECKED_BY_NONE:
                        checklist.pop(ck_key, None)
                    else:
                        checklist[ck_key] = cb_new
                    _save_all()
                    st.rerun()

            st.markdown("<div style='margin-bottom:.6rem;'></div>",
                        unsafe_allow_html=True)

    st.markdown("<hr style='margin:1rem 0;'>", unsafe_allow_html=True)

    # ── Daily fulfilment checklist ────────────────────────────────────────────
    d_key   = f"daily_{date_key}"
    ds      = checklist.get(d_key, {})

    DAILY_ITEMS = [
        ("partial_contracts", "📋 Partially Live Contracts Posted?"),
        ("oneoff_contracts",  "📄 One Off / Sale Contracts Posted?"),
    ]
    mcs_check_count = int(ds.get("mcs_check", 0))

    all_daily_done = (
        all(ds.get(k, False) for k, _ in DAILY_ITEMS)
        and mcs_check_count >= 1
    )

    st.markdown(
        f"<div style='font-size:13px;font-weight:700;color:{K_GREY};"
        f"margin-bottom:.6rem;'>📋 Daily Fulfilment Checklist</div>",
        unsafe_allow_html=True)

    if all_daily_done:
        st.markdown("""
        <div class="day-complete-banner">
          <div class="day-complete-title">🎉 Dailys Complete!</div>
          <div class="day-complete-sub">All daily fulfilment tasks done for this day.</div>
        </div>
        """, unsafe_allow_html=True)

    daily_changed = False
    dc_cols = st.columns(len(DAILY_ITEMS))
    for ci, (ck, label) in enumerate(DAILY_ITEMS):
        with dc_cols[ci]:
            cur    = ds.get(ck, False)
            newval = st.checkbox(label, value=cur, key=f"dcl_{date_key}_{ck}")
            if newval != cur:
                ds[ck] = newval
                daily_changed = True

    # MCS match counter
    st.markdown("<div style='margin-top:.5rem'></div>", unsafe_allow_html=True)
    mcs_c1, mcs_c2 = st.columns([5, 1])
    with mcs_c1:
        count_colour = K_GREEN_DARK if mcs_check_count >= 2 else ("#b45309" if mcs_check_count == 1 else "#9ca3af")
        count_bg     = K_GREEN_PALE if mcs_check_count >= 2 else ("#fef3c7" if mcs_check_count == 1 else "#f3f4f6")
        count_label  = f"✅ Checked {mcs_check_count}×" if mcs_check_count > 0 else "☐  Not yet checked"
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:10px;padding:6px 10px;"
            f"background:{count_bg};border-radius:8px;'>"
            f"<span style='font-size:13px;font-weight:600;color:{K_GREY};flex:1;'>"
            f"🔍 Prep Schedule Matches MCS?</span>"
            f"<span style='font-size:12px;font-weight:700;color:{count_colour};"
            f"background:white;border-radius:5px;padding:2px 10px;"
            f"border:1px solid {count_colour};white-space:nowrap;'>{count_label}</span>"
            f"</div>", unsafe_allow_html=True)
    with mcs_c2:
        if st.button("＋ Check", key=f"mcs_check_{date_key}", use_container_width=True):
            ds["mcs_check"] = mcs_check_count + 1
            daily_changed = True

    if daily_changed:
        checklist[d_key] = ds
        save_data(jobs, mcs, site_visits, svr_confirmed, checklist, live_hire, materials, materials_totals)
        st.rerun()

    st.markdown("<hr style='margin:1rem 0;'>", unsafe_allow_html=True)

    # ── Site Visit Requests for this day ─────────────────────────────────────
    sv_list = site_visits.get(date_key, [])
    if sv_list:
        st.markdown(
            f"<div style='font-size:13px;font-weight:700;color:{K_PURPLE_DARK};"
            f"margin-bottom:.5rem;'>🔍 Site Visit Requests</div>",
            unsafe_allow_html=True)
        for svi, sv in enumerate(sv_list):
            svr_key       = f"{date_key}_{svi}"
            is_confirmed  = svr_confirmed.get(svr_key, False)
            conf_badge    = ""
            if is_confirmed:
                conf_badge = (f'<div style="margin-top:8px;display:inline-flex;'
                              f'align-items:center;gap:6px;background:#f3e8ff;'
                              f'color:{K_PURPLE_DARK};border-radius:6px;'
                              f'padding:4px 10px;font-size:11px;font-weight:700;">'
                              f'✅ Nathan Checked and Confirmed in Diary</div>')

            time_str = f" — {sv['time_on_site']}" if sv.get("time_on_site") else ""
            st.markdown(f"""
            <div style="background:{K_PURPLE_PALE};color:{K_PURPLE_DARK};
                        border-radius:10px;border-left:4px solid {K_PURPLE};
                        padding:12px 14px;margin-bottom:6px;">
              <div style="font-size:16px;font-weight:800;margin-bottom:2px;">
                {sv.get("customer","")}{time_str}</div>
              <div style="font-size:11px;opacity:.7;margin-bottom:4px;">
                {sv.get("site_contact","")}{"  ·  " if sv.get("site_contact") else ""}
                {sv.get("site_address","")}</div>
              <div style="font-size:12px;margin-bottom:4px;">{sv.get("description","")}</div>
              <div style="font-size:10px;opacity:.5;">
                🕐 Requested by {sv.get("requested_by","")} · {sv.get("timestamp","")}</div>
              {conf_badge}
            </div>
            """, unsafe_allow_html=True)

            sc1, sc2, sc3, sc4 = st.columns([3, 2, 1, 1])
            with sc1:
                if not is_confirmed:
                    if st.button("✅ Nathan Checked and Confirmed in Diary",
                                 key=f"svr_confirm_{svr_key}", use_container_width=True):
                        svr_confirmed[svr_key] = True
                        save_data(jobs, mcs, site_visits, svr_confirmed, checklist, live_hire, materials, materials_totals)
                        st.rerun()
                else:
                    if st.button("↩ Unconfirm", key=f"svr_unconfirm_{svr_key}",
                                 use_container_width=True):
                        svr_confirmed.pop(svr_key, None)
                        save_data(jobs, mcs, site_visits, svr_confirmed, checklist, live_hire, materials, materials_totals)
                        st.rerun()
            with sc2:
                if st.button("✏️ Edit request", key=f"svr_edit_{svr_key}",
                             use_container_width=True):
                    st.session_state["svr_modal_date"] = date_key
                    st.session_state["svr_token"] = _uuid.uuid4().hex[:8]
                    st.session_state["any_dialog_open"] = True
                    st.session_state["svr_modal_idx"]  = svi
                    st.session_state["day_view_date"]  = None
                    st.rerun()
            with sc3:
                if st.button("📅", key=f"svr_move_{svr_key}",
                             use_container_width=True, help="Move to another day"):
                    st.session_state["msv_from_date"]   = date_key
                    st.session_state["msv_idx"]         = svi
                    st.session_state["msv_token"]       = _uuid.uuid4().hex[:8]
                    st.session_state["any_dialog_open"] = True
                    st.session_state["day_view_date"]   = None
                    st.rerun()

        st.markdown("<div style='margin-top:.5rem'></div>", unsafe_allow_html=True)

    st.markdown("<hr style='margin:.75rem 0;'>", unsafe_allow_html=True)
    ac1, ac2, ac3 = st.columns(3)
    with ac1:
        if st.button("＋ Add job to this day", use_container_width=True, type="primary"):
            st.session_state["modal_date"]       = date_key
            st.session_state["modal_edit_idx"]   = None
            st.session_state["modal_token"]      = _uuid.uuid4().hex[:8]
            st.session_state["any_dialog_open"]  = True
            st.session_state["day_view_date"]    = None
            st.rerun()
    with ac2:
        if st.button("🔍 Request Site Visit", use_container_width=True):
            st.session_state["svr_modal_date"] = date_key
            st.session_state["svr_token"] = _uuid.uuid4().hex[:8]
            st.session_state["any_dialog_open"] = True
            st.session_state["svr_modal_idx"]  = None
            st.session_state["day_view_date"]  = None
            st.rerun()
    with ac3:
        if st.button("Close", use_container_width=True):
            close_dialog(day_view_date=None)
            st.rerun()

# ── SITE VISIT REQUEST DIALOG (add/edit) ─────────────────────────────────────
@st.dialog("Site Visit Request", width="large")
def site_visit_dialog(date_key, edit_svr_idx=None):
    edit_sv = None
    if edit_svr_idx is not None:
        sv_list = site_visits.get(date_key, [])
        if edit_svr_idx < len(sv_list):
            edit_sv = sv_list[edit_svr_idx]

    day_label = datetime.strptime(date_key, "%Y-%m-%d").strftime("%A %-d %B %Y")
    st.markdown(
        f"<div style='font-size:13px;color:{K_PURPLE_DARK};font-weight:700;"
        f"background:{K_PURPLE_PALE};border-radius:6px;padding:6px 12px;"
        f"margin-bottom:1rem;'>🔍 Site Visit Request — 📅 {day_label}</div>",
        unsafe_allow_html=True)

    if edit_sv and edit_sv.get("requested_by"):
        st.markdown(
            f"<div style='font-size:11px;color:{K_GREY};opacity:.55;"
            f"background:#f5f5f5;border-radius:5px;padding:4px 8px;"
            f"margin-bottom:.75rem;display:inline-block;'>"
            f"🕐 Requested by <b>{edit_sv['requested_by']}</b>"
            f"{' at ' + edit_sv.get('timestamp','') if edit_sv.get('timestamp') else ''}</div>",
            unsafe_allow_html=True)

    sv1, sv2 = st.columns(2)
    with sv1:
        customer = st.text_input("Customer *",
                                 value=edit_sv.get("customer", "") if edit_sv else "")
    with sv2:
        site_contact = st.text_input("Site Contact",
                                     value=edit_sv.get("site_contact", "") if edit_sv else "")

    site_address = st.text_input("Site Address *",
                                 value=edit_sv.get("site_address", "") if edit_sv else "")

    ta1, ta2 = st.columns([3, 1])
    with ta1:
        description = st.text_area("Description / Purpose of Visit",
                                   value=edit_sv.get("description", "") if edit_sv else "",
                                   height=100)
    with ta2:
        time_on_site = st.text_input("Time on Site",
                                     value=edit_sv.get("time_on_site", "") if edit_sv else "",
                                     placeholder="e.g. 10:30")

    name_opts = ["— Select your name *"] + TEAM_MEMBERS
    def_name  = edit_sv.get("requested_by", "—") if edit_sv else "—"
    name_idx  = name_opts.index(def_name) if def_name in name_opts else 0
    requested_by = st.selectbox("Requested by *", name_opts, index=name_idx)

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
    sb1, sb2, sb3 = st.columns([2, 2, 2])
    with sb1:
        if st.button("✅ Save Request", type="primary", use_container_width=True):
            errors = []
            if not customer.strip():
                errors.append("Please enter a customer name.")
            if not site_address.strip():
                errors.append("Please enter a site address.")
            if requested_by == "— Select your name *":
                errors.append("Please select who is making this request.")
            if errors:
                for e in errors:
                    st.warning(e)
            else:
                new_sv = {
                    "customer":     customer.strip(),
                    "site_contact": site_contact.strip(),
                    "site_address": site_address.strip(),
                    "description":  description.strip(),
                    "time_on_site": time_on_site.strip(),
                    "requested_by": requested_by,
                    "timestamp":    edit_sv.get("timestamp", datetime.now().strftime("%d/%m/%Y %H:%M")) if edit_sv else datetime.now().strftime("%d/%m/%Y %H:%M"),
                }
                if date_key not in site_visits:
                    site_visits[date_key] = []
                if edit_svr_idx is not None:
                    site_visits[date_key][edit_svr_idx] = new_sv
                else:
                    site_visits[date_key].append(new_sv)
                save_data(jobs, mcs, site_visits, svr_confirmed, checklist, live_hire, materials, materials_totals)
                st.session_state["day_view_date"]    = None
                st.session_state["svr_modal_date"]   = None
                st.session_state["svr_modal_idx"]    = None
                st.rerun()
    with sb2:
        if st.button("Cancel", use_container_width=True):
            st.session_state["svr_modal_date"] = None
            st.session_state["svr_modal_idx"]  = None
            st.rerun()
    with sb3:
        if edit_sv is not None:
            if st.button("🗑 Delete", use_container_width=True):
                site_visits[date_key].pop(edit_svr_idx)
                if not site_visits[date_key]:
                    del site_visits[date_key]
                save_data(jobs, mcs, site_visits, svr_confirmed, checklist, live_hire, materials, materials_totals)
                st.session_state["svr_modal_date"] = None
                st.session_state["svr_modal_idx"]  = None
                st.rerun()

# ── MOVE SITE VISIT DIALOG ────────────────────────────────────────────────────
@st.dialog("Move Site Visit to Another Day", width="small")
def move_site_visit_dialog(from_date, sv_idx):
    sv_list = site_visits.get(from_date, [])
    if sv_idx >= len(sv_list):
        st.warning("Site visit not found."); return

    sv       = sv_list[sv_idx]
    from_dt  = datetime.strptime(from_date, "%Y-%m-%d").date()

    st.markdown(
        f"<div style='background:{K_PURPLE_PALE};color:{K_PURPLE_DARK};border-radius:8px;"
        f"padding:10px 14px;margin-bottom:1rem;font-weight:700;font-size:14px;"
        f"border-left:4px solid {K_PURPLE};'>"
        f"🔍 {sv.get('customer','')} &nbsp;·&nbsp; "
        f"<span style='font-weight:400;font-size:12px;'>"
        f"{from_dt.strftime('%A %-d %B %Y')}</span></div>",
        unsafe_allow_html=True)

    st.markdown("**Move to:**")
    to_date = st.date_input("New date", value=from_dt, key="msv_to_date",
                            label_visibility="collapsed")

    if to_date == from_dt:
        st.info("Pick a different date to move this visit.")

    mc1, mc2 = st.columns(2)
    with mc1:
        if st.button("✅ Confirm Move", type="primary", use_container_width=True,
                     disabled=(to_date == from_dt)):
            to_key = fmt_key(to_date)
            # Move the visit
            sv_to_move = site_visits[from_date].pop(sv_idx)
            if not site_visits[from_date]:
                del site_visits[from_date]
            site_visits.setdefault(to_key, []).append(sv_to_move)
            # Move any confirmation status
            old_svr_key = f"{from_date}_{sv_idx}"
            new_svr_key = f"{to_key}_{len(site_visits[to_key]) - 1}"
            if old_svr_key in svr_confirmed:
                svr_confirmed[new_svr_key] = svr_confirmed.pop(old_svr_key)
            save_data(jobs, mcs, site_visits, svr_confirmed, checklist, live_hire, materials, materials_totals)
            st.session_state["msv_from_date"] = None
            st.session_state["msv_idx"]       = None
            st.session_state["day_view_date"] = None
            st.success(f"Moved to {to_date.strftime('%a %-d %b')}.")
            st.rerun()
    with mc2:
        if st.button("Cancel", use_container_width=True):
            st.session_state["msv_from_date"] = None
            st.session_state["msv_idx"]       = None
            st.rerun()

# ── MOVE JOB DIALOG ──────────────────────────────────────────────────────────
@st.dialog("Move Job to Another Day", width="small")
def move_job_dialog(from_date, job_idx):
    if from_date not in jobs or job_idx >= len(jobs[from_date]):
        st.warning("Job not found."); return

    job       = jobs[from_date][job_idx]
    from_dt   = datetime.strptime(from_date, "%Y-%m-%d").date()
    from_label = from_dt.strftime("%A %-d %B %Y")
    bg, fg, _ = TYPE_STYLE[job["type"]]

    st.markdown(
        f"<div style='background:{bg};color:{fg};border-radius:8px;"
        f"padding:10px 14px;margin-bottom:1rem;font-weight:700;font-size:14px;'>"
        f"{job.get('customer','')} &nbsp;·&nbsp; "
        f"<span style='font-weight:400;font-size:12px;'>{from_label}</span></div>",
        unsafe_allow_html=True)

    st.markdown("**Move to:**")
    to_date = st.date_input("New date", value=from_dt, key="move_to_date",
                            label_visibility="collapsed")

    if to_date == from_dt:
        st.info("Pick a different date to move this job.")

    mc1, mc2 = st.columns(2)
    with mc1:
        if st.button("✅ Confirm Move", type="primary", use_container_width=True,
                     disabled=(to_date == from_dt)):
            to_key = fmt_key(to_date)
            # Remove from source
            job_to_move = jobs[from_date].pop(job_idx)
            if not jobs[from_date]:
                del jobs[from_date]
            # Stamp the move
            job_to_move["moved_by"]   = "—"   # no user context here
            job_to_move["moved_from"] = from_date
            job_to_move["edited_at"]  = datetime.now().strftime("%d/%m/%Y %H:%M")
            # Add to destination
            jobs.setdefault(to_key, []).append(job_to_move)
            save_jobs(jobs)
            st.session_state["day_view_date"]  = None
            st.session_state["move_from_date"] = None
            st.session_state["move_job_idx"]   = None
            st.success(f"Moved to {to_date.strftime('%a %-d %b')}.")
            st.rerun()
    with mc2:
        if st.button("Cancel", use_container_width=True):
            st.session_state["move_from_date"] = None
            st.session_state["move_job_idx"]   = None
            st.rerun()

# ── EXPAND CHIP DIALOG (view details + open edit) ────────────────────────────
@st.dialog("Job Details", width="small")
def expand_chip_dialog(date_key, job_idx):
    if date_key not in jobs or job_idx >= len(jobs[date_key]):
        st.warning("Job not found."); return
    job = jobs[date_key][job_idx]
    bg, fg, _ = TYPE_STYLE[job["type"]]

    haulage = job.get("haulage", "None")
    border_col = K_GREEN if haulage == "Internal Haulage" else ("#c0392b" if haulage == "External Haulage" else K_LGREY)

    day_label = datetime.strptime(date_key, "%Y-%m-%d").strftime("%A %-d %B %Y")
    st.markdown(f"<div style='font-size:12px;color:{K_GREY};opacity:.5;margin-bottom:.5rem;'>📅 {day_label}</div>", unsafe_allow_html=True)

    # Big detail card
    units_html = ""
    if job.get("units"):
        unit_items = "".join(
            f'<span style="display:inline-block;background:{bg};color:{fg};'
            f'border-radius:4px;padding:2px 8px;font-size:11px;font-weight:600;'
            f'margin:2px;">{u} ×{q}</span>'
            for u, q in job["units"].items() if q
        )
        units_html = f"<div style='margin-top:8px;'>{unit_items}</div>"

    tags = f'<span style="background:rgba(0,0,0,.08);border-radius:4px;padding:2px 8px;font-size:11px;font-weight:700;">{job["type"]}</span>'
    if job.get("install_dismantle"):
        tags += f' <span style="background:{K_GREEN};color:white;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:700;">I/D</span>'
    if haulage != "None":
        haul_bg = K_GREEN_PALE if haulage == "Internal Haulage" else "#fdecea"
        haul_fg = K_GREEN_DARK if haulage == "Internal Haulage" else "#7b1a1a"
        haul_icon = "🚛" if haulage == "Internal Haulage" else "🚚"
        tags += f' <span style="background:{haul_bg};color:{haul_fg};border-radius:4px;padding:2px 8px;font-size:11px;font-weight:700;">{haul_icon} {haulage}</span>'

    st.markdown(f"""
    <div style="background:{bg};color:{fg};border-radius:10px;
                border-left:5px solid {border_col};padding:14px 16px;">
      <div style="font-size:20px;font-weight:800;margin-bottom:4px;">{job.get("customer","")}</div>
      <div style="font-size:13px;opacity:.7;margin-bottom:10px;">{job.get("postcode","")}</div>
      <div style="margin-bottom:8px;">{tags}</div>
      {units_html}
    </div>
    """, unsafe_allow_html=True)

    if job.get("added_by") or job.get("timestamp"):
        who = job.get("added_by","")
        ts  = job.get("timestamp","")
        st.markdown(f"<div style='font-size:11px;color:{K_GREY};opacity:.5;margin-top:8px;'>🕐 Added by <b>{who}</b> · {ts}</div>", unsafe_allow_html=True)
    if job.get("edited_at"):
        st.markdown(f"<div style='font-size:11px;color:{K_GREY};opacity:.5;'>✏️ Edited by <b>{job.get('edited_by','')}</b> · {job['edited_at']}</div>", unsafe_allow_html=True)

    # Queries raised against this job
    _eq = _queries_for_job(date_key, job_idx)
    for _qid, _q in _eq:
        if _q.get("status") == "open":
            st.markdown(
                f'<div style="margin-top:8px;padding:7px 9px;background:#fdecea;'
                f'border-left:3px solid #c0392b;border-radius:5px;font-size:11.5px;'
                f'color:#7b1a1a;"><b>❗ Query from {_q.get("raised_by","")}</b> '
                f'<span style="opacity:.6;">{_q.get("raised_at","")}</span>'
                f'<div style="margin-top:2px;">{_q.get("question","")}</div></div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div style="margin-top:8px;padding:7px 9px;'
                f'background:{K_GREEN_PALE};border-left:3px solid {K_GREEN};'
                f'border-radius:5px;font-size:11.5px;color:{K_GREEN_DARK};">'
                f'<div style="opacity:.75;">❓ {_q.get("raised_by","")}: '
                f'{_q.get("question","")}</div><div style="margin-top:3px;">'
                f'<b>💬 {_q.get("answered_by","")}</b> '
                f'<span style="opacity:.6;">{_q.get("answered_at","")}</span>'
                f'<br>{_q.get("answer","")}</div></div>',
                unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        if st.button("✏️ Edit this job", use_container_width=True, type="primary"):
            st.session_state["modal_date"]      = date_key
            st.session_state["modal_edit_idx"]  = job_idx
            st.session_state["modal_token"]     = _uuid.uuid4().hex[:8]
            st.session_state["any_dialog_open"] = True
            st.session_state["expand_date"]     = None
            st.session_state["expand_idx"]      = None
            st.rerun()
    with ec2:
        _eq_open = any(q.get("status") == "open" for _, q in _eq)
        if st.button("❗ Query" if _eq_open else "❓ Query",
                     use_container_width=True):
            st.session_state["query_date"]      = date_key
            st.session_state["query_idx"]       = job_idx
            st.session_state["query_token"]     = _uuid.uuid4().hex[:8]
            st.session_state["any_dialog_open"] = True
            st.session_state["expand_date"]     = None
            st.session_state["expand_idx"]      = None
            st.rerun()
    with ec3:
        if st.button("Close", use_container_width=True):
            st.session_state["expand_date"] = None
            st.session_state["expand_idx"]  = None
            st.rerun()

# ── JOB QUERY DIALOG ──────────────────────────────────────────────────────────
# The yard raises a question against a job; the day it sits on pulses red on
# the schedule until somebody in the office answers it. The answer comes back
# on the job itself, and the yard clears it once they have read it.
@st.dialog("Job Query", width="small")
def job_query_dialog(date_key, job_idx):
    if date_key not in jobs or job_idx >= len(jobs[date_key]):
        st.warning("Job not found."); return
    job = jobs[date_key][job_idx]
    bg, fg, _ = TYPE_STYLE[job["type"]]

    day_label = datetime.strptime(date_key, "%Y-%m-%d").strftime("%A %-d %B %Y")
    cn = str(job.get("contract_number") or "").strip()
    cn_html = ("" if cn in ("", "00000") else
               f'<span style="font-size:12px;font-weight:600;opacity:.6;'
               f'margin-left:8px;background:rgba(0,0,0,.07);border-radius:4px;'
               f'padding:1px 7px;">{cn}</span>')
    st.markdown(
        f'<div style="font-size:11px;color:{K_GREY};opacity:.55;'
        f'margin-bottom:.4rem;">📅 {day_label}</div>'
        f'<div style="background:{bg};color:{fg};border-radius:9px;'
        f'padding:10px 13px;margin-bottom:.8rem;">'
        f'<div style="font-size:16px;font-weight:800;">'
        f'{job.get("customer","")}{cn_html}</div>'
        f'<div style="font-size:11.5px;opacity:.7;">'
        f'{job.get("postcode","")} · {job.get("type","")}</div></div>',
        unsafe_allow_html=True)

    existing = _queries_for_job(date_key, job_idx)

    # ── Live and answered queries ────────────────────────────────────────────
    for qid, q in existing:
        if q.get("status") == "open":
            st.markdown(
                f'<div style="padding:8px 10px;background:#fdecea;'
                f'border-left:4px solid #c0392b;border-radius:6px;'
                f'font-size:12px;color:#7b1a1a;margin-bottom:.4rem;">'
                f'<b>❗ LIVE — {q.get("raised_by","")}</b> '
                f'<span style="opacity:.6;">{q.get("raised_at","")}</span>'
                f'<div style="margin-top:3px;">{q.get("question","")}</div></div>',
                unsafe_allow_html=True)
            st.markdown(
                f"<div style='font-size:11px;font-weight:700;color:{K_GREY};"
                f"opacity:.7;'>Office answer</div>", unsafe_allow_html=True)
            ans = st.text_area("Answer", key=f"qa_txt_{qid}", height=90,
                               label_visibility="collapsed",
                               placeholder="Answer for the yard…")
            ac1, ac2 = st.columns([2, 3])
            with ac1:
                who = st.selectbox("Answered by", QUERY_OFFICE,
                                   key=f"qa_who_{qid}",
                                   label_visibility="collapsed")
            with ac2:
                if st.button("💬 Send Answer", key=f"qa_send_{qid}",
                             type="primary", use_container_width=True):
                    if not ans.strip():
                        st.error("Type an answer first.")
                    else:
                        q["answer"]      = ans.strip()
                        q["answered_by"] = who
                        q["answered_at"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                        q["status"]      = "answered"
                        queries[qid]     = q
                        _save_all()
                        st.rerun()
            _query_delete_button(qid)
        else:
            st.markdown(
                f'<div style="padding:8px 10px;background:{K_GREEN_PALE};'
                f'border-left:4px solid {K_GREEN};border-radius:6px;'
                f'font-size:12px;color:{K_GREEN_DARK};margin-bottom:.4rem;">'
                f'<div style="opacity:.75;">❓ {q.get("raised_by","")} · '
                f'{q.get("raised_at","")}<br>{q.get("question","")}</div>'
                f'<div style="margin-top:5px;padding-top:5px;'
                f'border-top:1px solid rgba(0,0,0,.08);">'
                f'<b>💬 {q.get("answered_by","")}</b> '
                f'<span style="opacity:.6;">{q.get("answered_at","")}</span>'
                f'<br>{q.get("answer","")}</div></div>',
                unsafe_allow_html=True)
            if st.button("👍 Got it — clear", key=f"qc_{qid}",
                         use_container_width=True):
                q["status"]    = "closed"
                q["closed_at"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                queries[qid]   = q
                _save_all()
                st.rerun()
            _query_delete_button(qid)
        st.markdown("<hr style='margin:.7rem 0;'>", unsafe_allow_html=True)

    # ── Raise a new query ────────────────────────────────────────────────────
    st.markdown(
        f"<div style='font-size:12px;font-weight:700;color:{K_GREY};'>"
        f"❓ Raise a query</div>", unsafe_allow_html=True)
    nq = st.text_area("New query", key=f"qn_txt_{date_key}_{job_idx}", height=90,
                      label_visibility="collapsed",
                      placeholder="What do you need to know about this job?")
    nc1, nc2 = st.columns([2, 3])
    with nc1:
        nq_who = st.selectbox("Raised by", QUERY_YARD,
                              key=f"qn_who_{date_key}_{job_idx}",
                              label_visibility="collapsed")
    with nc2:
        if st.button("❗ Raise Query", type="primary", use_container_width=True,
                     key=f"qn_send_{date_key}_{job_idx}"):
            if not nq.strip():
                st.error("Type your question first.")
            else:
                qid = _uuid.uuid4().hex[:10]
                queries[qid] = {
                    "id":        qid,
                    "date":      date_key,
                    "job_idx":   job_idx,
                    "job":       _job_query_ref(job),
                    "raised_by": nq_who,
                    "raised_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "question":  nq.strip(),
                    "status":    "open",
                    "answer":    "",
                }
                _save_all()
                st.rerun()

    st.markdown("<div style='margin-top:.6rem'></div>", unsafe_allow_html=True)
    if st.button("Close", use_container_width=True, key=f"q_close_{date_key}_{job_idx}"):
        st.session_state["query_date"] = None
        st.session_state["query_idx"]  = None
        st.session_state["day_view_date"] = date_key
        st.session_state["dv_token"]   = _uuid.uuid4().hex[:8]
        st.rerun()

# ── MODAL DIALOG ──────────────────────────────────────────────────────────────
@st.dialog("Add / Edit Job", width="large")
def job_modal(date_key, edit_idx=None):
    edit_job = None
    if edit_idx is not None and date_key in jobs and edit_idx < len(jobs[date_key]):
        edit_job = jobs[date_key][edit_idx]

    # Unique key prefix — prevents widget key collisions across multiple opens
    _k = f"{date_key}_{edit_idx if edit_idx is not None else 'new'}"

    day_label = datetime.strptime(date_key, "%Y-%m-%d").strftime("%A %-d %B %Y")
    st.markdown(f"<div style='font-size:13px;color:{K_GREY};opacity:.6;"
                f"margin-bottom:1rem;'>📅 {day_label}</div>", unsafe_allow_html=True)

    # Show existing timestamp if editing
    if edit_job and edit_job.get("added_by"):
        ts  = edit_job.get("timestamp", "")
        who = edit_job.get("added_by", "")
        ts_str = f" at {ts}" if ts else ""
        st.markdown(
            f"<div style='font-size:11px;color:{K_GREY};opacity:.55;"
            f"background:#f5f5f5;border-radius:5px;padding:4px 8px;"
            f"margin-bottom:.75rem;display:inline-block;'>"
            f"🕐 Added by <b>{who}</b>{ts_str}</div>",
            unsafe_allow_html=True)

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        customer = st.text_input("Customer *",
                                 value=edit_job.get("customer", "") if edit_job else "")
    with fc2:
        postcode = st.text_input("Postcode",
                                 value=edit_job.get("postcode", "") if edit_job else "")
    with fc3:
        def_type = edit_job.get("type", "On Hire") if edit_job else "On Hire"
        job_type = st.selectbox("Type *", JOB_TYPES, index=JOB_TYPES.index(def_type))

    contract_number = st.text_input(
        "Contract Number",
        value=edit_job.get("contract_number", "00000") if edit_job else "00000",
        placeholder="00000"
    )

    # Site Move sub-type
    site_move_type = None
    if job_type == "Site Move":
        sm_opts = ["Movement on Same Site", "Movement to New Site"]
        def_sm  = edit_job.get("site_move_type", sm_opts[0]) if edit_job else sm_opts[0]
        if def_sm not in sm_opts:
            def_sm = sm_opts[0]
        site_move_type = st.radio(
            "Movement type",
            sm_opts,
            index=sm_opts.index(def_sm),
            horizontal=True,
            key=f"sm_{_k}",
        )

    # Mandatory Added By — always shown, pre-selected if editing
    name_opts = ["— Select your name *"] + TEAM_MEMBERS
    if edit_job and edit_job.get("added_by") in TEAM_MEMBERS:
        name_default = name_opts.index(edit_job["added_by"])
    else:
        name_default = 0
    added_by = st.selectbox("Added by *", name_opts, index=name_default)

    st.markdown(f"<div style='font-size:13px;font-weight:700;color:{K_GREY};"
                f"margin:1rem 0 .5rem;'>Units</div>", unsafe_allow_html=True)

    unit_vals = {}
    av_configs = {}   # { "32ft AV": {"Office": 2, "Canteen": 1}, ... }

    u_cols = st.columns(4)
    for i, u in enumerate(UNIT_TYPES):
        with u_cols[i % 4]:
            def_qty = int(edit_job.get("units", {}).get(u, 0)) if edit_job else 0
            unit_vals[u] = st.number_input(u, min_value=0, max_value=99,
                                           value=def_qty, step=1, key=f"mu_{_k}_{u}")

    # AV configuration breakdown — shown for any AV unit with qty > 0
    av_units_with_qty = [u for u in AV_UNITS if unit_vals.get(u, 0) > 0]
    if av_units_with_qty:
        st.markdown(
            f"<div style='font-size:12px;font-weight:700;color:{K_GREEN};"
            f"background:{K_GREEN_PALE};border-radius:6px;padding:6px 10px;"
            f"margin:.75rem 0 .5rem;'>AV Unit Configuration</div>",
            unsafe_allow_html=True)

        for u in av_units_with_qty:
            qty = unit_vals[u]
            st.markdown(
                f"<div style='font-size:12px;font-weight:600;color:{K_GREY};"
                f"margin:.5rem 0 .25rem;'>{u} — {qty} unit{'s' if qty > 1 else ''}"
                f" <span style='font-weight:400;opacity:.6;'>(assign configurations below)</span></div>",
                unsafe_allow_html=True)

            saved_cfg = (edit_job.get("av_configs", {}).get(u, {}) if edit_job else {})
            cfg_vals  = {}
            cfg_cols  = st.columns(4)
            for j, cfg in enumerate(AV_CONFIGS):
                with cfg_cols[j % 4]:
                    def_cfg = int(saved_cfg.get(cfg, 0))
                    cfg_vals[cfg] = st.number_input(
                        cfg, min_value=0, max_value=int(qty),
                        value=def_cfg, step=1, key=f"cfg_{_k}_{u}_{cfg}")

            # Validation hint
            cfg_total = sum(cfg_vals.values())
            if cfg_total > 0:
                if cfg_total == qty:
                    st.markdown(
                        f"<div style='font-size:10px;color:{K_GREEN};margin-top:2px;'>"
                        f"✓ {cfg_total}/{qty} assigned</div>", unsafe_allow_html=True)
                else:
                    st.markdown(
                        f"<div style='font-size:10px;color:#c0392b;margin-top:2px;'>"
                        f"⚠ {cfg_total}/{qty} assigned — totals don't match</div>",
                        unsafe_allow_html=True)

            av_configs[u] = {cfg: v for cfg, v in cfg_vals.items() if v > 0}

    def_id = edit_job.get("install_dismantle", False) if edit_job else False
    install_dismantle = st.checkbox("Install / Dismantle", value=def_id,
                                    key=f"id_{_k}")

    haulage_opts = ["None", "Internal Haulage", "External Haulage"]
    def_haulage  = edit_job.get("haulage", "None") if edit_job else "None"
    if def_haulage not in haulage_opts:
        def_haulage = "None"
    haulage = st.radio("Haulage", haulage_opts,
                       index=haulage_opts.index(def_haulage),
                       horizontal=True, key=f"haul_{_k}")
    haulage_who = ""
    if haulage == "External Haulage":
        haulage_who = st.text_input(
            "Who is the haulage contractor? *",
            value=edit_job.get("haulage_who", "") if edit_job else "",
            placeholder="e.g. Stobbarts, Eddie Stobart, XYZ Haulage...",
            key=f"hw_{_k}"
        )

    st.markdown(f"<div style='font-size:13px;font-weight:700;color:{K_GREY};"
                f"margin:1rem 0 .5rem;'>Cabin Livery</div>", unsafe_allow_html=True)
    livery_opts = ["Standard Livery", "Customer Livery — Specify"]
    def_livery  = edit_job.get("livery", "Standard Livery") if edit_job else "Standard Livery"
    if def_livery not in livery_opts:
        def_livery = "Standard Livery"
    livery = st.radio("Cabin livery", livery_opts,
                      index=livery_opts.index(def_livery),
                      horizontal=True,
                      label_visibility="collapsed",
                      key=f"liv_{_k}")
    livery_note = ""
    if livery == "Customer Livery — Specify":
        livery_note = st.text_input(
            "Paint colour or RAL code",
            value=edit_job.get("livery_note", "") if edit_job else "",
            placeholder="e.g. RAL 5010, British Racing Green, #1A2B3C…",
            key=f"livnote_{_k}"
        )

    # Notes
    notes_val = edit_job.get("notes", "") if edit_job else ""
    notes = st.text_area(
        "Notes (max 200 characters)",
        value=notes_val,
        max_chars=200,
        height=80,
        placeholder="Any additional details, instructions or context...",
        key=f"notes_{_k}"
    )
    chars_left = 200 - len(notes)
    st.markdown(
        f"<div style='font-size:10px;color:{'#c0392b' if chars_left < 20 else K_GREY};"
        f"opacity:.6;text-align:right;margin-top:-8px;'>{chars_left} characters remaining</div>",
        unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
    ba1, ba2, ba3 = st.columns([2, 2, 2])

    with ba1:
        if st.button("✅ Save Job", type="primary", use_container_width=True):
            errors = []
            if not customer.strip():
                errors.append("Please enter a customer name.")
            if added_by == "— Select your name *":
                errors.append("Please select who is adding this entry.")
            if haulage == "External Haulage" and not haulage_who.strip():
                errors.append("Please specify who the external haulage contractor is.")
            # AV config validation — configs must equal unit qty if any configs entered
            for av_u in av_units_with_qty:
                qty       = unit_vals[av_u]
                cfg_total = sum(av_configs.get(av_u, {}).values())
                if cfg_total > 0 and cfg_total != qty:
                    errors.append(
                        f"{av_u}: {cfg_total} layout{'s' if cfg_total != 1 else ''} assigned "
                        f"but {qty} unit{'s' if qty != 1 else ''} selected — please make them match."
                    )
                elif cfg_total == 0 and qty > 0:
                    errors.append(
                        f"{av_u}: please assign a layout configuration for "
                        f"{'all' if qty > 1 else 'this'} {qty} unit{'s' if qty != 1 else ''}."
                    )
            if errors:
                for e in errors:
                    st.warning(e)
            else:
                # Preserve original timestamp/added_by if editing, otherwise stamp now
                if edit_job and edit_idx is not None:
                    orig_ts      = edit_job.get("timestamp", "")
                    orig_by      = edit_job.get("added_by", added_by)
                    edited_ts    = datetime.now().strftime("%d/%m/%Y %H:%M")
                    edited_by    = added_by
                else:
                    orig_ts   = datetime.now().strftime("%d/%m/%Y %H:%M")
                    orig_by   = added_by
                    edited_ts = None
                    edited_by = None

                new_job = {
                    "customer":          customer.strip(),
                    "postcode":          postcode.strip().upper(),
                    "contract_number":   contract_number.strip(),
                    "type":              job_type,
                    "site_move_type":    site_move_type or "",
                    "units":             {u: v for u, v in unit_vals.items() if v > 0},
                    "av_configs":        av_configs,
                    "install_dismantle": install_dismantle,
                    "haulage":           haulage,
                    "haulage_who":       haulage_who.strip() if haulage == "External Haulage" else "",
                    "livery":            livery,
                    "livery_note":       livery_note.strip() if livery == "Customer Livery — Specify" else "",
                    "notes":             notes.strip(),
                    "added_by":          orig_by,
                    "timestamp":         orig_ts,
                }
                # Track notes edit — if notes changed during an edit, stamp it
                if edit_job is not None and notes.strip() != (edit_job.get("notes","") or ""):
                    new_job["notes_edited_by"] = added_by
                    new_job["notes_edited_at"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                elif edit_job is not None:
                    # Preserve existing notes edit stamp
                    if edit_job.get("notes_edited_by"):
                        new_job["notes_edited_by"] = edit_job["notes_edited_by"]
                        new_job["notes_edited_at"] = edit_job["notes_edited_at"]
                if edited_ts:
                    new_job["edited_by"] = edited_by
                    new_job["edited_at"] = edited_ts

                if date_key not in jobs:
                    jobs[date_key] = []
                if edit_idx is not None:
                    jobs[date_key][edit_idx] = new_job
                else:
                    jobs[date_key].append(new_job)
                save_jobs(jobs)
                st.session_state["modal_date"]     = None
                st.session_state["modal_edit_idx"] = None
                st.rerun()

    with ba2:
        if st.button("Cancel", use_container_width=True):
            st.session_state["modal_date"]     = None
            st.session_state["modal_edit_idx"] = None
            st.rerun()

    with ba3:
        if edit_job is not None:
            if st.button("🗑 Delete", use_container_width=True):
                jobs[date_key].pop(edit_idx)
                if not jobs[date_key]:
                    del jobs[date_key]
                save_jobs(jobs)
                st.session_state["modal_date"]     = None
                st.session_state["modal_edit_idx"] = None
                st.rerun()

# ── MATERIALS REQUEST — ADD DIALOG ───────────────────────────────────────────
MAT_RECEIVED_TTL_HOURS = 24   # received requests drop off after this


def _mat_received_expired(req):
    """True if this is a received request older than the TTL."""
    if req.get("status") != "pod_received":
        return False
    try:
        ts = datetime.strptime(req.get("pod_received_at", ""),
                               "%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return False      # undateable: keep it rather than lose it
    return (datetime.now() - ts) > timedelta(hours=MAT_RECEIVED_TTL_HOURS)


def _mat_purge_received():
    """Remove expired received requests. Called only alongside writes
    that are happening anyway, so no extra saves and no write races."""
    for m in [m for m, r in materials.items() if _mat_received_expired(r)]:
        materials.pop(m, None)


def _mat_request_key(req):
    """Identity of the REQUEST an item belongs to. Newer items carry a
    request_id; older ones fall back to requester + timestamp."""
    return (req.get("request_id")
            or f"{req.get('requester','')}|{req.get('created_at','')}")


def _mat_line_state(r):
    """One line's lifecycle. Ken (the PO worker) stamps po_number and
    po_status on each line; a line whose PO exists but is not yet
    approved shows the X.
      pending    no PO yet (red)
      awaiting   PO raised, NOT approved: the X
      ordered    PO approved (or marked ordered by hand)
      delivered  ticked Delivered in the app (legacy pod_received too)
    """
    if r.get("delivered") or r.get("status") == "pod_received":
        return "delivered"
    if r.get("status") == "ordered":
        return "ordered"
    if r.get("po_number"):
        return "awaiting"
    if r.get("query") and not r.get("query_answer"):
        return "query"      # Ken is asking: is this the right item?
    return "pending"


def _mat_group_state(members):
    """The whole request: green only when EVERY line is delivered; red
    while any line has no PO; amber in between."""
    states = {_mat_line_state(r) for _, r in members}
    if states and states <= {"delivered"}:
        return "delivered"
    if "pending" in states or "query" in states:
        return "pending"
    return "ordered"


MAT_LINE_MARK = {"pending": "", "awaiting": "❌", "ordered": "✔",
                 "delivered": "✅", "query": "❓"}

# Ken stamps po_link on each line. This is the fallback shape for older
# lines stamped before that field existed, and it is the same URL the PO
# emails use.
ZAHARA_PO_LINK = "https://myzahara.net/v3/documents/purchase-orders/view/{oid}"


def _po_link_html(r):
    """The PO number as a clickable link into Zahara, so Chris can go
    straight to the order from the schedule instead of searching for it
    (Nathan, 17/08/2026).

    Returns TRUSTED HTML: the number and the URL are both escaped here,
    so the caller must insert this without escaping it again. Falls back
    to plain text when there is no link to give, which is the case for
    the older lines Ken stamped before po_link existed and for anything
    marked ordered by hand.
    """
    num = _html_esc.escape(str(r.get("po_number", "")))
    link = str(r.get("po_link") or "").strip()
    if not link and r.get("po_order_id"):
        link = ZAHARA_PO_LINK.format(oid=r["po_order_id"])
    if not link.startswith("https://"):
        return f"PO {num}"
    href = _html_esc.escape(link, quote=True)
    return (f'PO <a href="{href}" target="_blank" rel="noopener noreferrer" '
            f'style="color:inherit;text-decoration:underline;'
            f'text-underline-offset:2px;font-weight:800;" '
            f'title="Open this purchase order in Zahara">{num}</a>')


def _mat_group_members(mid):
    """All items belonging to the same request as `mid`, newest
    request order preserved."""
    req = materials.get(mid)
    if not req:
        return []
    key = _mat_request_key(req)
    return [(m, r) for m, r in materials.items()
            if _mat_request_key(r) == key]


def _mat_save_lines(requester, final):
    """Persist a request: one entry per item, all sharing a request_id
    so status and actions apply to the request as a whole."""
    now_stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    rid = _uuid.uuid4().hex[:12]
    for ln in final:
        mid = _uuid.uuid4().hex[:12]
        materials[mid] = {
            "requester":  requester,
            "request_id": rid,
            "item":       f"{ln['quantity']} × {ln['item_name']}",
            "category":   ln["category"],
            "item_name":  ln["item_name"],
            "quantity":   ln["quantity"],
            "notes":      ln["notes"],
            "supplier":   ln["supplier"],
            "status":     "pending",
            "created_at": now_stamp,
        }
    _mat_purge_received()
    save_data(jobs, mcs, site_visits, svr_confirmed, checklist,
              live_hire, materials, materials_totals)


# ── MATERIALS REQUEST — BASKET-STYLE ADD DIALOG ──────────────────────────────
# One trip: search or browse the range, tick items, set quantities,
# and everything collects in the basket below. Submit sends the lot
# as a single request (Nathan, 14/08/2026).

ITEM_INDEX = []
for _top, _subs in DANFAST_TREE.items():
    for _sub, _names in _subs.items():
        for _nm in _names:
            ITEM_INDEX.append((_nm, _top, _sub))
for _top, _names in OTHER_CATEGORIES.items():
    for _nm in _names:
        ITEM_INDEX.append((_nm, _top, ""))


def _mb_key(name):
    return _hashlib.md5(str(name).encode()).hexdigest()[:12]


def _mat_basket_reset():
    st.session_state["mat_basket"] = {}
    for k in list(st.session_state):
        if k.startswith(("mbt_", "mbq_", "mbrm_")):
            st.session_state.pop(k, None)
    for k in ("mat_search", "mat_custom_desc", "mat_custom_qty",
              "mat_req_notes"):
        st.session_state.pop(k, None)


@st.dialog("New Materials Request", width="large")
def materials_add_dialog():
    name_opts = ["— Select your name *"] + MATERIALS_NAMES
    requester = st.selectbox("Your name *", name_opts, key="mat_name")
    basket = st.session_state.setdefault("mat_basket", {})

    # a basket-row ❌ queued a removal: process it BEFORE any checkbox
    # renders, so its widget state can be cleared safely
    rm = st.session_state.pop("mat_basket_rm", None)
    if rm is not None:
        basket.pop(rm, None)
        st.session_state.pop("mbt_" + _mb_key(rm), None)
        st.session_state.pop("mbq_" + _mb_key(rm), None)

    def item_rows(rows):
        """Tickable item rows; ticking shows a qty box and drops the
        item straight into the basket."""
        for nm, top, sub in rows:
            k = _mb_key(nm)
            c1, c2 = st.columns([7, 2], vertical_alignment="center")
            with c1:
                on = st.checkbox(nm, value=nm in basket,
                                 key=f"mbt_{k}", help=(sub or top))
            with c2:
                if on:
                    q0 = basket.get(nm, {}).get("qty", 1)
                    qv = st.number_input(
                        "Qty", min_value=1, step=1, value=int(q0),
                        key=f"mbq_{k}", label_visibility="collapsed")
                    basket[nm] = {"qty": int(qv), "category": top}
            if not on and nm in basket:
                basket.pop(nm, None)

    st.text_input("🔍 Search the whole range", key="mat_search",
                  placeholder="e.g. barrier pipe, downflow heater, "
                              "M8 bolts, door handle...")
    q = (st.session_state.get("mat_search") or "").strip()

    if len(q) >= 2:
        toks = q.lower().split()

        def _in(t, nm, top, sub):
            return t in nm.lower() or t in sub.lower() \
                or t in top.lower()

        hits = [(nm, top, sub) for nm, top, sub in ITEM_INDEX
                if all(_in(t, nm, top, sub) for t in toks)]
        loose = False
        if not hits and len(toks) > 1:
            # nothing matches every word: show close matches instead
            # ("m8 bolt" still finds the M8 setscrews)
            loose = True
            hits = [(nm, top, sub) for nm, top, sub in ITEM_INDEX
                    if any(_in(t, nm, top, sub) for t in toks)]
        # best first: most words in the NAME itself, shortest name wins
        hits.sort(key=lambda r: (
            -sum(1 for t in toks if t in r[0].lower()), len(r[0])))
        st.caption(
            (f"No exact match for '{q}', showing close matches · "
             if loose else "")
            + f"{len(hits)} match(es)"
            + (", showing the first 25" if len(hits) > 25 else "")
            + " · clear the search to browse")
        item_rows(hits[:25])
    else:
        bc1, bc2 = st.columns(2)
        browse_opts = [c for c in FORM_CATEGORY_ORDER
                       if c != ANYTHING_ELSE]
        with bc1:
            category = st.selectbox(
                "Category", ["— Browse by category"] + browse_opts,
                key="mat_cat_browse",
                format_func=lambda c: FORM_CAT_LABELS.get(c, c))
        rows = []
        if category in DANFAST_TREE:
            subs = DANFAST_TREE[category]
            with bc2:
                if len(subs) > 1:
                    sub = st.selectbox(
                        "Type", ["— Select type"] + sorted(subs),
                        key=f"mat_sub_browse_{_mb_key(category)}",
                        format_func=lambda s:
                        (f"{s}  ({len(subs[s])})" if s in subs else s))
                else:
                    sub = list(subs)[0]
            if sub in subs:
                rows = [(nm, category, sub) for nm in subs[sub]]
        elif category in OTHER_CATEGORIES:
            rows = [(nm, category, "")
                    for nm in OTHER_CATEGORIES[category]]
        item_rows(rows)

    with st.expander("➕ Can't find it? Add anything"):
        cc1, cc2, cc3 = st.columns([6, 2, 2],
                                   vertical_alignment="bottom")
        with cc1:
            custom = st.text_input(
                "Describe it", key="mat_custom_desc",
                placeholder="e.g. 8x4 marine ply, odd bracket...")
        with cc2:
            cqty = st.number_input("Qty", min_value=1, step=1,
                                   value=1, key="mat_custom_qty")
        with cc3:
            if st.button("Add ➕", use_container_width=True,
                         key="mat_custom_addbtn"):
                if custom.strip():
                    basket[custom.strip()[:120]] = {
                        "qty": int(cqty), "category": ANYTHING_ELSE}
                    st.session_state["mat_add"] = True
                    st.rerun()

    # ── the basket: everything ticked so far ─────────────────────────
    st.markdown("---")
    if basket:
        st.markdown(
            f"##### 🧺 This request · {len(basket)} line"
            f"{'s' if len(basket) != 1 else ''}, "
            f"{sum(v['qty'] for v in basket.values())} item"
            f"{'s' if sum(v['qty'] for v in basket.values()) != 1 else ''}")
        for nm, info in list(basket.items()):
            b1, b2 = st.columns([9, 1], vertical_alignment="center")
            with b1:
                st.markdown(
                    f"<div style='background:{K_GREEN_PALE};"
                    f"border-radius:6px;padding:5px 10px;"
                    f"font-size:13px;'><b>{info['qty']} ×</b> "
                    f"{_html_esc.escape(nm)} "
                    f"<span style='opacity:.5;font-size:11px;'>"
                    f"({_html_esc.escape(info['category'])})</span></div>",
                    unsafe_allow_html=True)
            with b2:
                if st.button("❌", key=f"mbrm_{_mb_key(nm)}",
                             help="Remove from the request"):
                    st.session_state["mat_basket_rm"] = nm
                    st.session_state["mat_add"] = True
                    st.rerun()
    else:
        st.caption("Nothing ticked yet. Search or browse above, tick "
                   "what you need, and it collects here.")

    st.text_area("Notes for the whole request", key="mat_req_notes",
                 placeholder="Which unit or job it is for, colours, "
                             "sizes...")

    mc1, mc2 = st.columns(2)
    with mc1:
        if st.button(f"✅ Submit Request ({len(basket)})",
                     type="primary", use_container_width=True,
                     disabled=not basket):
            if requester == "— Select your name *":
                st.warning("Please select your name.")
            else:
                notes = (st.session_state.get("mat_req_notes")
                         or "").strip()
                final = [{"category": v["category"], "item_name": nm,
                          "quantity": v["qty"], "notes": notes,
                          "supplier": ""}
                         for nm, v in basket.items()]
                _mat_save_lines(requester, final)
                _mat_basket_reset()
                st.session_state["any_dialog_open"] = False
                st.rerun()
    with mc2:
        if st.button("Cancel", use_container_width=True):
            _mat_basket_reset()
            st.session_state["any_dialog_open"] = False
            st.rerun()

# ── MATERIALS REQUEST — VIEW/UPDATE DIALOG ────────────────────────────────────
@st.dialog("Materials Request", width="small")
def materials_view_dialog(mid):
    req = materials.get(mid)
    if not req:
        st.warning("Request not found."); return

    # The whole REQUEST is the unit for display, but each LINE carries
    # its own PO, approval state and Delivered tick. The pill only
    # turns green when every line is delivered.
    members = _mat_group_members(mid)
    g_state = _mat_group_state(members)
    status_colours = {
        "pending":   ("#fdecea", "#7b1a1a"),
        "ordered":   ("#fff9e6", "#7a5c00"),
        "delivered": (K_GREEN_PALE, K_GREEN_DARK),
    }
    bg, fg = status_colours.get(g_state, ("#f0f0f0", K_GREY))
    status_label = {"pending": "🔴 Pending", "ordered": "🟡 On Order",
                    "delivered": "🟢 Delivered"}

    n_delivered = sum(1 for _m, r in members
                      if _mat_line_state(r) == "delivered")
    n_awaiting = sum(1 for _m, r in members
                     if _mat_line_state(r) == "awaiting")

    st.markdown(f"""
    <div style="background:{bg};color:{fg};border-radius:8px 8px 0 0;padding:12px 14px 8px;">
      <div style="font-size:12px;opacity:.7;">Requested by <b>{req.get("requester","")}</b> · {req.get("created_at","")}</div>
      <div style="font-size:10px;opacity:.55;">{len(members)} item{"s" if len(members) != 1 else ""} on this request · {n_delivered} delivered{f" · {n_awaiting} awaiting PO approval" if n_awaiting else ""} · tap 📦 when an item arrives</div>
    </div>
    """, unsafe_allow_html=True)

    # one row per line, the 📦 tick ON the line itself: item text left,
    # the delivered button (or its ✅ once ticked) right
    st.markdown(
        "<style>"
        "[class*='st-key-mat_dlv_'] button,"
        "[class*='st-key-mat_undlv_'] button{padding:2px 4px !important;"
        "min-height:30px !important;height:30px !important;"
        "border:1px solid rgba(0,0,0,.15) !important;"
        "border-radius:6px !important;background:rgba(255,255,255,.7) "
        "!important;font-size:15px !important;}"
        "[class*='st-key-mat_row_'] {margin-bottom:-12px !important;}"
        "</style>", unsafe_allow_html=True)
    for m, r in members:
        state = _mat_line_state(r)
        mark = MAT_LINE_MARK.get(state, "")
        # detail is inserted as HTML below, so anything from the record is
        # escaped here and only _po_link_html contributes real markup
        detail = []
        if r.get("category"):
            detail.append(_html_esc.escape(str(r["category"])))
        if r.get("po_number"):
            detail.append(
                _po_link_html(r)
                + (f' · {_html_esc.escape(str(r.get("po_supplier","")))}'
                   if r.get("po_supplier") else "")
                + (" · awaiting approval" if state == "awaiting" else ""))
        elif r.get("supplier"):
            detail.append(_html_esc.escape(str(r["supplier"])))
        if state == "delivered":
            detail.append(_html_esc.escape(
                f'Delivered {r.get("delivered_at") or r.get("pod_received_at","")}'))
        q = r.get("query") or {}
        query_html = ""
        if state == "query":
            price_bit = (f' at £{q.get("candidate_price"):.2f}'
                         if isinstance(q.get("candidate_price"),
                                       (int, float)) else "")
            query_html = (
                f'<div style="background:rgba(255,255,255,.75);'
                f'border-radius:6px;padding:5px 8px;margin-top:4px;'
                f'font-size:12px;font-weight:700;">'
                f'Ken asks: is this '
                f'"{_html_esc.escape(str(q.get("candidate_name","")))}"'
                f'{price_bit}?</div>')
        line_html = (
            f'<div style="background:{bg};color:{fg};'
            f'padding:5px 14px 6px;">'
            f'<div style="border-top:1px solid rgba(0,0,0,.08);'
            f'padding-top:5px;">'
            f'<div style="font-size:15px;font-weight:800;">'
            f'{mark + " " if mark else ""}{r.get("item","")}</div>'
            + (f'<div style="font-size:11px;opacity:.6;">'
               f'{" · ".join(detail)}</div>' if detail else "")
            + (f'<div style="font-size:11px;opacity:.6;">'
               f'{r["notes"]}</div>' if r.get("notes") else "")
            + query_html
            + '</div></div>')
        row = st.container(key=f"mat_row_{m}")
        with row:
            lc, rc = st.columns([8, 1], vertical_alignment="center")
            with lc:
                st.markdown(line_html, unsafe_allow_html=True)
                if state == "query":
                    qc1, qc2 = st.columns(2)
                    with qc1:
                        if st.button("✔ Yes, that's it",
                                     key=f"matq_yes_{m}",
                                     use_container_width=True):
                            r["query_answer"] = "yes"
                            r["confirmed_code"] = q.get("candidate_code")
                            r["query_answered_at"] = datetime.now() \
                                .strftime("%d/%m/%Y %H:%M")
                            materials[m] = r
                            save_data(jobs, mcs, site_visits,
                                      svr_confirmed, checklist,
                                      live_hire, materials,
                                      materials_totals)
                            st.session_state["mat_view_id"] = mid
                            st.session_state["any_dialog_open"] = True
                            st.rerun()
                    with qc2:
                        if st.button("✖ No, not that",
                                     key=f"matq_no_{m}",
                                     use_container_width=True):
                            r["query_answer"] = "no"
                            r["query_answered_at"] = datetime.now() \
                                .strftime("%d/%m/%Y %H:%M")
                            materials[m] = r
                            save_data(jobs, mcs, site_visits,
                                      svr_confirmed, checklist,
                                      live_hire, materials,
                                      materials_totals)
                            st.session_state["mat_view_id"] = mid
                            st.session_state["any_dialog_open"] = True
                            st.rerun()
            with rc:
                if state != "delivered":
                    if st.button("📦", key=f"mat_dlv_{m}",
                                 help="Tick this item as delivered"):
                        stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
                        r["delivered"] = True
                        r["delivered_at"] = stamp
                        materials[m] = r
                        _mat_purge_received()
                        save_data(jobs, mcs, site_visits, svr_confirmed,
                                  checklist, live_hire, materials,
                                  materials_totals)
                        # reopen this dialog so several lines can be
                        # ticked in one sitting
                        st.session_state["mat_view_id"] = mid
                        st.session_state["any_dialog_open"] = True
                        st.rerun()
                else:
                    if st.button("✅", key=f"mat_undlv_{m}",
                                 help="Untick - not delivered after all"):
                        r.pop("delivered", None)
                        r.pop("delivered_at", None)
                        if r.get("status") == "pod_received":
                            # legacy lines delivered the old way go
                            # back to ordered, not to red
                            r["status"] = "ordered"
                            r.pop("pod_received_at", None)
                        materials[m] = r
                        save_data(jobs, mcs, site_visits, svr_confirmed,
                                  checklist, live_hire, materials,
                                  materials_totals)
                        st.session_state["mat_view_id"] = mid
                        st.session_state["any_dialog_open"] = True
                        st.rerun()

    st.markdown(f"""
    <div style="background:{bg};color:{fg};border-radius:0 0 8px 8px;padding:8px 14px 12px;margin-bottom:1rem;">
      <div style="font-size:12px;font-weight:700;">{status_label.get(g_state,"")}</div>
      {f'<div style="font-size:10px;opacity:.6;">Ordered by {req.get("ordered_by","")} · {req.get("ordered_at","")}</div>' if req.get("ordered_by") else ""}
    </div>
    """, unsafe_allow_html=True)

    if g_state == "pending":
        st.markdown("**Or mark the whole request as Ordered by hand:**")
        orderer = st.selectbox("Ordered by",
                               ["— Select *"] + MATERIALS_ORDERERS,
                               key=f"mat_orderer_{mid}")
        if st.button("✅ Mark Ordered", type="primary", use_container_width=True):
            if orderer == "— Select *":
                st.warning("Please select who ordered it.")
            else:
                stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
                for m, r in members:
                    if _mat_line_state(r) in ("pending", "awaiting"):
                        r["status"]     = "ordered"
                        r["ordered_by"] = orderer
                        r["ordered_at"] = stamp
                        materials[m]    = r
                _mat_purge_received()
                save_data(jobs, mcs, site_visits, svr_confirmed, checklist, live_hire, materials, materials_totals)
                st.session_state["any_dialog_open"] = False
                st.rerun()

    st.markdown("<div style='margin-top:.75rem'></div>", unsafe_allow_html=True)
    dc1, dc2 = st.columns(2)
    with dc1:
        if st.button("🗑 Delete request", use_container_width=True):
            for m, _r in members:
                materials.pop(m, None)
            save_data(jobs, mcs, site_visits, svr_confirmed, checklist, live_hire, materials, materials_totals)
            st.session_state["any_dialog_open"] = False
            st.rerun()
    with dc2:
        if st.button("Close", use_container_width=True):
            st.session_state["any_dialog_open"] = False
            st.rerun()

# ── Trigger dialogs ───────────────────────────────────────────────────────────
# Each dialog key stores a (value, token) tuple. The token is a unique ID set
# when a button is clicked. We track the last rendered token — if it matches,
# the dialog is already open or was already closed, so we don't reopen it.
# This prevents auto-refresh re-opening dialogs while keeping them stable mid-form.

def _should_open(key, token_key):
    """Return True only if this dialog key has a new unrendered token."""
    val = st.session_state.get(key)
    if not val:
        return False
    token    = st.session_state.get(token_key, "")
    rendered = st.session_state.get(f"{token_key}_rendered", "")
    return token != rendered

def _mark_rendered(token_key):
    """Mark this dialog's token as rendered so it won't refire on auto-refresh."""
    st.session_state[f"{token_key}_rendered"] = st.session_state.get(token_key, "")

if _should_open("svr_modal_date", "svr_token"):
    _mark_rendered("svr_token")
    site_visit_dialog(st.session_state.svr_modal_date, st.session_state.svr_modal_idx)
elif _should_open("msv_from_date", "msv_token") and st.session_state.get("msv_idx") is not None:
    _mark_rendered("msv_token")
    move_site_visit_dialog(st.session_state.msv_from_date, st.session_state.msv_idx)
elif _should_open("move_from_date", "move_token") and st.session_state.get("move_job_idx") is not None:
    _mark_rendered("move_token")
    move_job_dialog(st.session_state.move_from_date, st.session_state.move_job_idx)
elif _should_open("day_view_date", "dv_token"):
    _mark_rendered("dv_token")
    day_view_dialog(st.session_state.day_view_date)
elif _should_open("query_date", "query_token") and st.session_state.get("query_idx") is not None:
    _mark_rendered("query_token")
    job_query_dialog(st.session_state.query_date, st.session_state.query_idx)
elif _should_open("expand_date", "expand_token") and st.session_state.get("expand_idx") is not None:
    _mark_rendered("expand_token")
    expand_chip_dialog(st.session_state.expand_date, st.session_state.expand_idx)
elif _should_open("modal_date", "modal_token"):
    _mark_rendered("modal_token")
    job_modal(st.session_state.modal_date, st.session_state.modal_edit_idx)
elif st.session_state.get("mat_add"):
    st.session_state["mat_add"] = False
    st.session_state["any_dialog_open"] = True
    materials_add_dialog()
elif st.session_state.get("mat_view_id"):
    mid = st.session_state["mat_view_id"]
    st.session_state["mat_view_id"] = None
    st.session_state["any_dialog_open"] = True
    materials_view_dialog(mid)
else:
    # No dialog is opening — safe to re-enable auto-refresh
    st.session_state["any_dialog_open"] = False

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("<style>[data-testid=\"stSidebar\"],[data-testid=\"collapsedControl\"]{display:none !important;}</style>", unsafe_allow_html=True)

# ── HEADER + SEARCH ──────────────────────────────────────────────────────────
# Search Version 1.2. Searches the WHOLE schedule (past and future, all
# weeks), not just the weeks currently on screen. Every space-separated
# term must match somewhere on the job: customer, contract number
# (splits like 31815#1 included), postcode, type, units, haulage,
# notes, livery, who added or edited it, or the date (2026-08-26,
# 26/08/2026, 26 Aug 2026 or the day name all work). V1.1: results are
# clickable - View opens the job in the same dialog as clicking it on
# the schedule. V1.2: search box moved into the header bar; results
# render as colour-coded pills in schedule styling. V1.3: search box
# sits tight against the title with a green outline, and the green
# header rule runs the full page width.

st.markdown(f"""
<style>
/* green outline on the header search box only - targeted by its
   placeholder text so it survives Streamlit DOM differences */
div[data-baseweb="input"]:has(input[placeholder*="Search Customer"]) {{
  border: 2px solid {K_GREEN} !important;
  border-radius: 8px;
  background: {K_WHITE} !important;
}}
div[data-baseweb="input"]:has(input[placeholder*="Search Customer"])
    input {{
  background: {K_WHITE} !important;
}}
div[data-baseweb="input"]:has(input[placeholder*="Search Customer"])
    :focus-within {{
  box-shadow: 0 0 0 3px {K_GREEN_PALE};
}}

</style>
""", unsafe_allow_html=True)

# ── YARD BOARD HEADER, 02/11/2026 ────────────────────────────────────────────
# The Yard Board redesign (approved on the Claude Design canvas, 02/11/2026).
# A green Kensite bar carries the real logo; the week controls and the
# search sit in one row beneath it. The date range is worked out here
# (it used to be below the nav row) because the header row shows it.
YB_LOGO_HTML = ('<img alt="Kensite" style="height:30px;width:auto;display:block;" '
                'src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAQkAAABICAYAAADlGwAZAAAWRklEQVR4nO2deZRlVXXGf/tVddNA0w1BcEBcYMhSNMRolLgcccxkInHFSJCAQaIgKlE0BBIcIIlAIkGCgiuAMjhlYYgSROOERgRjkDiARNAWUbBRhu6mge6uV1/+2GfXPfX6Tfe+96qq2/Ot9dab7j3z2Xef7+y9DywRSDJJLUnLJF0p6UXp92lJttjlKygoWGRImk7vZ8mxTtKr0m8mqbWoBSwoKFg8ZALisCQgtqjCu0NAxHUFBQW/QMgEwP6S1ktqS5pNr5kkKD4tac903bLFLXFBQcGCIS0jpiTtKOmGJBBCMARCq7hF0m+m+wpPUVCwkEiTtfZrDPnGMuP8LsuMboJiY8ZTtApPUVCwHSMTEEcOEBCBdvb59BBSRaMoKJgsYtdgF2AF0AaGnXQGbAAeAjAzDZuppCkza0t6EvDVlLcNkbeAWWAKuBI4wszulmR18i8oKBge8TQ+FXg9MANM45Mxn7DKr8cnagt4hZn9p6RpM5sZJsP05DdgJXAdsH+W3rCIcq4Bng/cBpiZzdZIo6CgYAjEluKOwK4N7o+dhjoq/5SZzUg6FxcQMeHrIPL7CXBP+l40iYKCCSAmZxufZMNO2Hjyt9P3oSZoaBySjgUOrZFft7zvAP7IzNZLapXlRkHBZJBPUGM4XqDutcAcDzGTtjHPxAXMVI2yQsVJtHA+Ym3wGzXTKSgoGBILsoWYyFFJ2h34MLCcmkImoY0LtpPN7HNJMykCoqBggpi4kEhEZSuRiucDj8Une928Q0BcaWZ/X4csLSgoaI6F0CRimfEW4GCch6i7zIhtz9uBI5PgKTsZBQULgIkKiYyHeA7wLpoJCKVXGzjMzO6i0kwKCgomjIl5VSYeYlbumHVpymuW5jzEW83sy2WZUVCwsJiIJpHxEAI+AOyNaxF184st0o+b2T8mU+5CVBYULCAmtdyIZcbbgd+luT3ENHALcFTSTNrFHqKgYGEx9uVGZjD1YuAdjMZDbAZeaWb3JX6jJw+ROXoZQOEsCgrGg7EKiXjaS9oLuBif6C2a8xBvMLOvZ4InFwS5nYUBSlyFUlmK09cvOGK8lHEwGsYmJDLHLcMFxMNpZlUZAuJSMzs3Jyqzzu7a6ZJWA3vgGsiPe123EFD3UHu1lks90uibTp97mkD9jNUkTdH9ATB0PdODpXPZ2zffAeko3T8bZQiOjMrHZ7au4Kjbn33aZlQM6pOx9/+4EjQqHuI03DOzCQ8RQuVG4JjQTGCuo3cBdgN2B/YB9gJ+GXgM8CjgEbhw+piZvWoxTbbHsQNTJ43QnMa989NPIxswWAdqcumaWUaweYnAQ93SiQmT2qTd8V+tsVG3XSc57gb0ydh3/sYlJKbM7CFJBwMn0ExARKUfAA41s/szadwG3g68GliNC4t+eERHmguC6DxJOwF/CeyMD1zhwu9cM/tBckgbxK+0gBPx+sbWcRv32P0XM7sx0snyXZHy3YXRjM2ivN8Dzu8clFk8kMOBA6jikBiuxf0DsL7fYM7SeBZuZLcl3T8FrDGz9w0SNPlEl7Q/8GLgqfhDY1eS+b+kdcBP8YfPV4DPm9mmYZcjkpYDb8HbNeraAi40s1vy/sz65E+BX6PZrl7XYuBt81Pc9ykvX/T/Krz/d2C0/p/FPbyvN7OPRCanp4hPg6JDBSJK1O9EISXtK+lueQDbdq8b+yDyPiqlOZXeI4LVGen/2fQ+k+7Zkj7H91lJ39QiRKxSFS1rN0mbu9TxeXndeqQR9X1Tj3b6tqRV8vB91pHvKkmbGrR9L1yT0m31KOOne9x3SX5dj3ouS+9v7XL/N/N69bg/Aig/V9Knatb7RklHdvZbn/5cKemBLunE+J/K7olxe1WN8tTBbX3KufeY87ocRtckonGncYOpX6IZDxGax/lmdr6kZWa2peOaW3EJ18alXLc8IljOw4FVwDotDoEp4Oc4P5IH7Oms0/ybfIC1Jf0KcGrH9QI2Agf3cY+3lO+ebB04qA6iD9f1Kmp6X4/3Xd7ns8Bhkq42swvU2/gt0ngopTFDpUnc3a9wqrSQk4FTsr8in171jjZ5AnCBpBcARwJbJPXTKATchS9v4wndwrWmXljH1m0zCsL7+Z4B16wHdmI8/X8fjEFIJCl2JvAMmvMQ08ANwBvTRMkHVXTc7QyvtgVvsY7FC0gzTRXlC4bzeg218X34UiU6awYXjMeZ2ffVfz2d55tHEqvTBsOGAphKecXkhsqE/mxJ16VlUb/ytqjGTKTTT9MKAXECLiAi3Vb23m2c5MuEeNgcirf5oUqeyn3qGu2aC4l+7WP0b8coSyd69dWwfTL2/h91rfQAsC8e+i4Sr4OoyHqch3gQtlojxuc703u/ModAWA48smGZFgWqtnmPAl5IJSBy79fzVN89Prahp2q8lqf3nRtUJdp7J+ASOU8yrujqrSQg9sc1rfAmDu5qOn3fgj8g1uPaV7RlXNfChe4W4E8kvTzxCON44gd2Yn5bdr56jeNefRXa88oGZRmp/0fVJHbE40weDFyAP73raBMxAV5rZjf3UU0BfoZ3+M70V6XCY3SbERKq7Ev2Bk6nUi2DsPwZcLTqeb/mGsxJwLephM4wmALWdqQ1LEL7eTJwppm9Ts5PjMq8R5u8Gp80sUQJ7eUc4JN41LJ703/LccJxP+ClwBFUWkBoD8dJuozxaJzRP6fgcyII2UCUdzVwHj7p8746HieMu/VVvyVgPxwH/ICq/QZBePv+qPplROIypfEEVQfsDJNOXHN2ur/ryVyqSJkdJP2gI/9+6R6f7luwowGzsu4q6a5UjjiNTJKenf6f6rgvyK7L03VxQFHU5ZBu93XJd7WktVkbRTs9bdQ69SjvxzvK29k3Uf6Xp+unszSC/DwuuzbS+VK3vLN6XqPqhLfIYx7j36c+b05l3JzluUHSo9P/rezayG9nST/u0q4vzNujDuTj+Z4uY+SJDdKKcu4lP5tGWXqS9Ni6aeYYi++GpBVmdhPwXOBjVGu3XpI5NIjrgOO1NQ8xh7RGNzPbhJNyw2KfGtcuFELtzg85WpZU6ENwjaxzmfERM/uoRovCtUp+WvuK9D7sa6oB6ZuPqajHeZIem5ZTjcdcjAWcc+pcn38ttedKScvlp7xNKR3iFPXBDf3An5TTVCr8fpFN0/LlSHlOdXlNp3JEHTqxKl23vMf9TZZEu6X671Cz/1swPjuJGfl6cT1wiKQbqVjnTnY3lgp34/EhtmhwINswqvoR8DSGUwtjubGUTLS3pHLkAnGL3J3+TOYvM1p4NPDjUmeNsu+9Ke0W9d1dGRHRvl8Enk1FaILvel0k3wKOiV4/g8oeYGP2c6R1OPBJM7u/y31T2bWbgCuAh1EFgJ5Ov+f1GAm97GCyOvQS+O300BinQdZDXXYLh8bYVPEw6sFdxE9NguIC3KglP88jnpBHJaZ+jodQbyOjGAi3p/d+HRnXPiYbjIu1w9GJPSQ9DBeaecTxf8KFWjv7bRo4xsx+ptEtR3fvyHcQoq02AJuHFLBR5rOB7wLHMn935lnA35rZX6n5EjDSuhH4DSpPYeHexjdI+jTwv7j38BpgbWq7aL8NuMbWFf2M3LZhPFzSWioOZhgYcJ+ZbR7rej0Npnaa+P8m6Xt44NsDqJ6e08AZZvbvQwqIHD8Zphh4Q+yJnwz2UJO6jBlRpg8xn8gKrWpXKou6mGznmdkVah5kJ9RxAZdQkXzDICbfb5vZtTWF1CNxS9FX4BpEpDUDnCDpS2Z2laQdqE9kxgC/GCcgw1s46vm49ApsAH4s6fvATbhwuRm4KTSOJLC29xAEn2D4to72NODpwM0TIfXS2nPazL4jD113IfCH6e+rgZOic2KNnjSR/czs1i7Lg/i8JrKgGiDK/o9J0MIH655mdpsG74EvBIze21fRMbEz8018Qg375B+U7yAz9l5oMj52N7MN8pimH6QyS44+uEDSU/AdmyhfJ7oKs6SGt8zsC5IuwgVFbicR/huxc7ELfgDU/sBLsqR+KOkq4Bwzuym18/YczKjJtikkfmliMS6ToJgys/vM7GXAabhn5mHpqTQXyi4JiGOBb0j647Rm6zZA76Ta94+BEAY9QULFxFqPq9nDGKAsFDoFW/4khEogfCXxO+OK5dmmsmoc5rUlvTfJe0US8hcBl1NpEbGMeiRwVprwRnerxX7jUmlSvwbfQsztH3INrZ29ol7BQewDHAP8t6RjU1nGaSOx1FC3/+MlmGCMS5iT/CEITpT0z2Z2R6Y9tBOLejZwdLrtPEk3dDjOhBbwc6qBcE/6/hN8Dzh/vxN3hNmAT7Sl/pQIfiJ2hV4j6UMNVP1eaDoBmoyPZUnIT+G8xIG4h24sO9rAKyR9zMwul/Rgum8oQZ7SFk4CHyPpX4GjgINSPr3KHFpGCOZZ3ObmHEntZKi2vQZYbtr/UzBhIQHVtlXqgDuS6t9Kmsaj8fXyQVRrpt2AD8ltCmZUuRODC4CDcOGwFrh3GxAAgX4GYNbx/zLgXElPx3c/RtmdEfAdXLMalsANbW1d9r0ups3sTklHAJ+l0hyjDO+RdCXdfREG9algzkT7i8AXJe0GPBHnJPbDz3fZBxcce+Ceka3s/tzE+t2SPmVmP9oOBYWAb+DcXF0C/35YACEBc4SmOgTEc3CnsL1x9TaMqWbwbc6z0pNizlLPzDYCX8rTTml2qpoCtITIqNAUXof7qMQaON5Pxtn5fDfgScBJZvY2NbNWjHZoAUeb2VebFLxDSNdBENifl3QK7uofu1xtvN9PAP6jQXmiX+eEiZndi7uBf6Xj+p3x0AH74uPqcODxVG0zg5tQvww4i+GtErcVGL7Ev7lpAgtpjdjCJ+6MpNfiW2XLqbw68zLN4GbI15rZxdK88HVz0Ydgm9uy+h8z+3rnj5KOBr6Fe67muxwnSPqEmV0/4rJjRWr/WgSdZdGdGqKdBNw7cQfAF1EJQuGxD6aZLzB7QlWshtNTWrFuXg5chJtlRzrCI1BtBL6fXp+TdA5Onj+ZShgofY/P2xt2jAc0NQRgzK2FOgs0gthOJf7hPFwwBJvfiejo90n61YwElZm1Y/AuIU1hEOacnjTfmq4labmZ3Y5vGwa5F9cvx5cdyxjNSSqEa63XqGRe6p8YlK/CfSpyn5SVwNsYfhzGdXvhk/ppOOfx68CT0lZxvvNlqqwcl0laaWYbcGOq2E0KLbTpDtC2gKb9P9ndjUBSD9uSHgVcBbyBrd17OxEdtzPwYUkrI61Jl3fCmA3DnhB2OOcwZWbnAZ9n/pM1ll5vTROgaX/dZ2YzZrYpvQ/7GpnvSXVsmdkdVLYNOYHYj6vphRvwNtpMtWvxAkl7m9lD2YNkNn2eMbMtVlljhtaQC5R+W7LbOu5NbbC5Zv/PwoSXG6r8FJ6N75nvy/BeorFePAB4r5kdkZ4GM9uQBjEQGVsPvhvwDZxky5cdJ0u6wsy+XYNYyzmal0s6gHoWl9P4lvVnopzD1mmrgvhDYtr8JPh34suPpmexgAvTEJixdNkbuFbShcBXcWJ7A9UDZzU+/l4K/D7z29eALzSr3TaBIyT9kOEtLiN83S3AlwHGEb5uq85W5cC0k6Q16fpuId0GIcr02pRuV2/RpQA19ALNf5N0fLp2puP9GlVOQ728I1er8gKd7Xhvgl7h67p5gUY/nZb+m+4so1ztN0mf6aibOr539QLNyyLpinRtjKlu9dyS/u/MJw+BKEm3yR3D5kICdrTr2LxAszT3kHRvVp4o04EjpNnLC7QpLoPJGlPJ3+wB/AkZDH/dJ1JI+7MkPcXcIWy7M3zJDHrOAq5l6x2QZ+CRqeqGQzMqY5phjWo2pff1o9ZrrhDz+YkjmM9P1EKaFG/EtYUIHhPp50Zg01TBWmapjMRg/qFRx6WlSBOv120Bdfs/lnH3w4Q5icRET5nZp/BIQk3MX0NdXIHzE6uguSfhAqKnBVsfxJkKR+MTNQb2bPp+sga7XPfLt+4EGHR9t0HXc9Jn/MRPcSIz0ojJm1tG9kvDzGwNHh37W7ggiK1wqIRFbnWZk5SGC5D7gSPM/YimrL+nZJP+HISFTnPYtOddvxC7G7Py9eg7cOIyiLk6CNb/ccD7Y6dkrKUcLwx3RY4n2bLsc++bKqH6LdyMfVn22gE3NLtMvvffTR3vzHe64WuH9L7rgHquzq5fkT73DXmX8ROfxY+BzNtnqHxTO7VSOz0L3xn6LtXk7zTT7zTd3wh8FDgwbbEP2l7O23V5esXnpmg0RgaghW+jj6v/V8HCWVyGG/mfAddTRR2uI6SC7T9EHmD1PWruITlpPAi8iercDfC63po+91Oxo63ehVsj7khFrs2m77sn68AweQ/J/yDw5izfptpWGBr9MPs+r4zp/Vyc8Ms9fK/tuKYb2kkTOhXfVdiFasdjmiokQE9kgmIDcJo8MtWB+LkbjwcejW+xLsOtDdfhDoI3ANckTYR+AiJr1014f+blbOGepYPq2gv342HlVmT3T1G1eZM07wX+gurcjab9Hyb035n7RRMgLjuhiuw6SPPPyKiDCFm2WdIz83QLfjEhJ0KbhI+bswMo6I8Fs7jM1MyrJZ0InEH9bbBYTy4DLpXHbrxbS9DevkNwhkQfevs2aQm9Bv9CnAVqVHYdXaH5513O8QF17Cu6lNdg7vDnwYWsYpiEwdBW5vnM5yLCZL/WeOmoa5SzPcq469FXI8W2GGP/g/flbCQ8cU2isxLaOuhrHcQ9n4g0tfSJzIKCbRKLoW7FevTVuD19k8AqwU/8gaQT01OnLDsKCiaABRcSSZVqmdk9wGFUe9xN7Sf+TtILw79jvKUtKChYFOImTejlZnYdflrzKPYTABdLegS+M1DIqIKCMWIxJ9QWOZF5NtVZHU3sJ2bxkGgfjN8KP1FQMD4smpDIWOkWHq/w/2imUQQ/8VvAKYWfKCgYLxZVNc/8O9YDr6QKf9+En5gB/kbS7xV+oqBgfFj09XtmP3E9bi3W88i/fslQOY9dKOkxFH6ioGAsWBKTyKpzOt4PfIDqxOg6CH5iT/wQnBajRXMqKChgiQiJhOAnXo8fTpNHMx4W+ZFypzdwqy4oKOjAkhESHfEnXknyZac+PxGBdI+X9LLCTxQUjIYlIyRgHj9xI37CUriI10VoFBdJempKd0nVtaBgW8GSmzgZP3Ep8F4qzaAO4tDdB4CVhZcoKGiOJSckEiKU25vx+BPDGlqJyrP0a8DTzexq0oHEEyprQcF2jSUpJBI/ITPbjPt33MfgI8ryoCWXAM83szWqzvwoKChogCUpJGAu8tC0+fFkf05/fqJNdajICWZ2OPCgPM7EtnJWaEHBksSSFRIwx08sM7PLgDPpzk+EGfZdwEvM7Iy0VClLjIKCMWBJC4mE2MI8Afgv5vMTwT98HXimmV2ZtI+RIgYVFBRUyI9in23wmvgZBRk/MYPbT/yc6iyJady68nlmdquWbmDcgoJtFiEkVqTPyxnuMNHp7HqY8PmJGT9xO35eQ5yQfZKZHWZmGxP/UAREQcGYEbEp1+LhxjcznBlzhBRfn32fKDL7iSsl/TWwxsw+kpYis2V5UVAwGVgKTBtHodXZCTCq06VqRx9uCmXnJGjwoSoFBQUj4v8BZhrn/UyDtaUAAAAASUVORK5CYII=">')
st.markdown(f"""
<div class="yb-bar">
  {YB_LOGO_HTML}
  <span class="yb-bar-title">Prep Schedule</span>
</div>
""", unsafe_allow_html=True)

today      = date.today()
start_date = get_monday(today) + timedelta(weeks=st.session_state.week_offset)
n_weeks    = st.session_state.n_weeks
end_date   = start_date + timedelta(days=n_weeks * 7 - 1)

n1, n2, n3, n4, n5, n6 = st.columns([1.1, 0.8, 1.1, 0.9, 1.9, 4.2],
                                    vertical_alignment="center")
with n1:
    if st.button("Prev Week", use_container_width=True):
        st.session_state.week_offset -= 1; st.rerun()
with n2:
    if st.button("Today", use_container_width=True):
        st.session_state.week_offset = 0; st.rerun()
with n3:
    if st.button("Next Week", use_container_width=True):
        st.session_state.week_offset += 1; st.rerun()
with n4:
    week_opts = [1, 2, 3, 4, 5, 6]
    nw = st.selectbox("Weeks Shown", week_opts,
                      index=week_opts.index(st.session_state.n_weeks)
                            if st.session_state.n_weeks in week_opts else 3,
                      label_visibility="collapsed",
                      format_func=lambda x: f"{x} {'Week' if x == 1 else 'Weeks'}")
    if nw != st.session_state.n_weeks:
        st.session_state.n_weeks = nw; st.rerun()
with n5:
    st.markdown(
        f"<div class='yb-range'>{start_date.strftime('%-d %b')} to "
        f"{end_date.strftime('%-d %b %Y')}</div>", unsafe_allow_html=True)
with n6:
    search_q = st.text_input(
        "Find a Job", key="job_search", label_visibility="collapsed",
        placeholder="Search Customer, Contract or Postcode")

def _job_search_hits(jobs_dict, query):
    hits = []
    terms = [t for t in query.lower().split() if t]
    if not terms:
        return hits
    for dk, jlist in sorted(jobs_dict.items()):
        try:
            d = datetime.strptime(dk, "%Y-%m-%d").date()
        except ValueError:
            continue
        date_blob = " ".join([
            dk, d.strftime("%d/%m/%Y"), d.strftime("%d/%m/%y"),
            d.strftime("%d %b %Y"), d.strftime("%d %B %Y"),
            d.strftime("%A")]).lower()
        for idx, j in enumerate(jlist or []):
            units_str = ", ".join(
                f"{u}×{q}" for u, q in (j.get("units") or {}).items() if q)
            blob = " ".join(str(x) for x in [
                j.get("customer", ""), j.get("contract_number", ""),
                j.get("postcode", ""), j.get("type", ""),
                j.get("site_move_type", ""), j.get("notes", ""),
                j.get("haulage", ""), j.get("haulage_who", ""),
                j.get("livery", ""), j.get("livery_note", ""),
                j.get("added_by", ""), j.get("edited_by", ""),
                units_str]).lower()
            if all(t in blob or t in date_blob for t in terms):
                hits.append({
                    "Date": d.strftime("%d/%m/%Y"),
                    "Day": d.strftime("%A"),
                    "Type": j.get("type", ""),
                    "Customer": j.get("customer", ""),
                    "Contract No.": j.get("contract_number", ""),
                    "Postcode": j.get("postcode", ""),
                    "Units": units_str,
                    "Haulage": j.get("haulage", ""),
                    "Notes": j.get("notes", ""),
                    "Added By": j.get("added_by", ""),
                    "_dk": dk,       # date key for click-to-open
                    "_idx": idx,     # position within that day's list
                })
    return hits


def _pill(text, bg="#f1f3f4", fg=K_GREY):
    return (f"<span style='background:{bg};color:{fg};border-radius:6px;"
            f"padding:3px 9px;font-size:12px;font-weight:700;"
            f"margin-right:6px;white-space:nowrap;display:inline-block;"
            f"margin-bottom:3px;'>{_html_esc.escape(str(text))}</span>")


if search_q.strip():
    search_hits = _job_search_hits(jobs, search_q)
    MAX_CLICKABLE = 30
    if not search_hits:
        st.info("No jobs match that search.")
    elif len(search_hits) > MAX_CLICKABLE:
        st.markdown(f"**{len(search_hits)} jobs found** - narrow the "
                    f"search to open one directly.")
        st.dataframe(
            pd.DataFrame(search_hits).drop(columns=["_dk", "_idx"]),
            use_container_width=True, hide_index=True)
    else:
        st.markdown(f"**{len(search_hits)} job(s) found** - click View "
                    f"to open a job as on the schedule.")
        for h in search_hits:
            bc1, bc2 = st.columns([1, 11])
            with bc1:
                if st.button("👁 View",
                             key=f"srch_{h['_dk']}_{h['_idx']}",
                             use_container_width=True):
                    open_dialog(expand_date=h["_dk"],
                                expand_idx=h["_idx"])
                    st.rerun()
            with bc2:
                tbg, tfg, _ = TYPE_STYLE.get(
                    h["Type"], ("#f1f3f4", K_GREY, ""))
                pills = [
                    _pill(h["Type"] or "Unknown", tbg, tfg),
                    _pill(f"{h['Day'][:3]} {h['Date']}",
                          K_GREEN_PALE, K_GREEN_DARK),
                    _pill(h["Customer"] or "No customer"),
                ]
                if h["Contract No."]:
                    pills.append(_pill(h["Contract No."]))
                if h["Postcode"]:
                    pills.append(_pill(h["Postcode"]))
                if h["Units"]:
                    pills.append(_pill(h["Units"]))
                if h["Haulage"] and h["Haulage"] != "None":
                    hbg, hfg = ((K_GREEN_PALE, K_GREEN_DARK)
                                if h["Haulage"] == "Internal Haulage"
                                else ("#fdecea", "#7b1a1a"))
                    pills.append(_pill(("🚛 " if h["Haulage"] ==
                                        "Internal Haulage" else "🚚 ")
                                       + h["Haulage"], hbg, hfg))
                st.markdown(
                    "<div style='padding-top:6px;'>" + "".join(pills)
                    + "</div>", unsafe_allow_html=True)

# ── REQUEST PANELS REMOVED, 09/10/2026 ───────────────────────────────────────
# The Live Hire Report, Request a Quote and Request Copy Invoice panels that
# sat here (three expanders across one row) were taken out at Nathan's
# request: Ken does all three on demand by email now. Each open page was
# reading three request queue files from GitHub to draw them, so dropping
# them also cuts the app's GitHub calls by three quarters (one file read
# per 30 s instead of four). The panels are in Archive/app before request
# panels removed 09-10-2026.py if they are ever wanted back.


# Summary pills removed 14/08/2026 (Nathan: obsolete) - the whole-file
# counts told nobody anything the week totals do not.

# ── Helper functions for fulfilment checks ────────────────────────────────────
def job_per_checks_done(dk, ji, job_type):
    """Return dict of per-job check states for a given job."""
    base = f"job_{dk}_{ji}"
    if job_type == "Off Hire":
        return {
            "poc":     checklist.get(f"{base}_poc", False),
            "returns": checklist.get(f"{base}_returns", False),
        }
    return {}

def daily_checklist_done(dk):
    """Return True if all daily items + mcs_check ≥ 1 for a given day."""
    d_key = f"daily_{dk}"
    ds    = checklist.get(d_key, {})
    return (
        ds.get("partial_contracts", False) and
        ds.get("oneoff_contracts",  False) and
        int(ds.get("mcs_check", 0)) >= 1
    )

def day_jobs_fulfilment_complete(dk):
    """All per-job checks done for all On/Off Hire jobs on this day."""
    day_job_list = jobs.get(dk, [])
    if not day_job_list:
        return True
    for ji, job in enumerate(day_job_list):
        jtype = job["type"]
        base  = f"job_{dk}_{ji}"
        if jtype == "Off Hire":
            poc_ok     = checklist.get(f"{base}_poc", False)
            returns_ok = checklist.get(f"{base}_returns", False)
            if not (poc_ok and returns_ok):
                return False
    return True

st.markdown("<div style='margin-bottom:.5rem'></div>", unsafe_allow_html=True)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def week_unit_summary(ws):
    on_u, off_u = {}, {}
    on_total = off_total = 0
    internal_assets = external_assets = 0
    for d in range(7):
        dk = fmt_key(ws + timedelta(days=d))
        for job in jobs.get(dk, []):
            is_off = job["type"] == "Off Hire"
            target = off_u if is_off else on_u
            h      = job.get("haulage", "None")
            for u, q in job.get("units", {}).items():
                if q:
                    target[u] = target.get(u, 0) + q
                    if is_off:
                        off_total += q
                    else:
                        on_total += q
                    # Count asset quantities by haulage — exclude accessories
                    if u in ASSET_UNITS:
                        if h == "Internal Haulage":
                            internal_assets += q
                        elif h == "External Haulage":
                            external_assets += q
    return on_u, off_u, on_total, off_total, internal_assets, external_assets

def render_week_bar(on_u, off_u, on_total, off_total, internal_assets, external_assets, lh_snapshot=None):
    if not on_u and not off_u and not internal_assets and not external_assets:
        return ""
    html = "<div class='wk-bar'><div style='display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap;'>"
    # Left — unit breakdown
    html += "<div style='flex:1;min-width:0;'><div class='wk-bar-title'>Week totals</div><div class='wk-unit-row'>"
    if on_u:
        html += (f"<span style='font-size:10px;font-weight:700;color:{K_GREEN_DARK};"
                 f"margin-right:3px;'>ON:</span>")
        html += "".join(f'<span class="wku">{u} ×{q}</span>' for u, q in on_u.items())
    if off_u:
        html += (f"<span style='font-size:10px;font-weight:700;color:#7a3a00;"
                 f"margin:0 3px;'>OFF:</span>")
        html += "".join(f'<span class="wku off">{u} ×{q}</span>' for u, q in off_u.items())
    html += "</div></div>"
    # Middle — asset delivery counts by haulage type
    html += (
        f"<div style='flex-shrink:0;border-left:1px solid #c3dfc9;padding-left:10px;'>"
        f"<div class='wk-bar-title'>Assets Moving</div>"
        f"<div style='display:flex;gap:6px;margin-top:2px;'>"
        f"<span style='background:{K_GREEN};color:white;border-radius:4px;"
        f"padding:2px 8px;font-size:10.5px;font-weight:600;'>🚛 {internal_assets} Internal</span>"
        f"<span style='background:#c0392b;color:white;border-radius:4px;"
        f"padding:2px 8px;font-size:10.5px;font-weight:600;'>🚚 {external_assets} External</span>"
        f"</div></div>"
    )
    # Right — asset totals + live hire revenue
    rev_html = ""
    if False and lh_snapshot and lh_snapshot.get("latest"):
        rev   = lh_snapshot["latest"].get("revenue", 0)
        ts    = lh_snapshot["latest"].get("at", "")
        rev_html = (
            f"<div style='font-size:11px;font-weight:800;color:{K_GREEN_DARK};"
            f"margin-top:4px;padding-top:4px;border-top:1px solid #c3dfc9;'>"
            f"💰 £{rev:,.2f}/wk live</div>"
            f"<div style='font-size:9px;color:{K_GREEN_DARK};opacity:.6;'>as at {ts}</div>"
        )
    html += (
        f"<div style='text-align:right;flex-shrink:0;white-space:nowrap;'>"
        f"<div style='font-size:10px;font-weight:700;color:{K_GREEN_DARK};margin-bottom:2px;'>"
        f"📦 {on_total} assets on hire</div>"
        f"<div style='font-size:10px;font-weight:700;color:#7b1a1a;'>"
        f"📦 {off_total} assets off hire</div>"
        f"{rev_html}"
        f"</div>"
    )
    html += "</div></div>"
    return html

# ── YARD BOARD, 02/11/2026 ───────────────────────────────────────────────────
# Each day is a column of job rows: type and arrow, time slot, customer,
# units, postcode, haulier, MCS tag, Checked By and query state. Clicking a
# row opens the job (the same dialog search uses). Open queries show as a
# number in a red circle on the day. A thin band after Friday opens the
# weekend. Time slots read Unknown until Ken can read ETAs from the AES
# Planner (the slot is there ready for it).
YB_TYPE = {
    "On Hire":   ("#0a6a30", "M7 17L17 7M9 7h8v8"),
    "Off Hire":  ("#a61b1b", "M17 7L7 17M15 17H7V9"),
    "Site Move": ("#1d5fae", "M4 9h14l-3-3M20 15H6l3 3"),
}
YB_DAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _yb_svg(path, colour, size=13, width=2.6):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{colour}" stroke-width="{width}" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true"><path d="{path}"/></svg>')


YB_CLOCK = ('<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" '
            'stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" '
            'r="9"/><path d="M12 7v5l3 2"/></svg>')
YB_TICK = "M5 12l5 5 9-10"


def _yb_qty(job_list, jtype):
    return sum(int(q or 0) for j in job_list if j.get("type") == jtype
               for q in (j.get("units") or {}).values())


def _yb_job_html(dk, ji, job):
    e = _html_esc.escape
    jtype = job.get("type", "On Hire")
    colour, arrow = YB_TYPE.get(jtype, ("#40424a", "M5 12h14"))
    label = jtype
    if job.get("site_move_type"):
        label += f" · {job['site_move_type']}"
    units = ", ".join(f"{q} × {u}" for u, q in (job.get("units") or {}).items() if q)
    h = job.get("haulage", "None")
    haul = ("Kensite HIAB" if h == "Internal Haulage"
            else (job.get("haulage_who") or "External") if h == "External Haulage"
            else "")
    meta = [x for x in [job.get("postcode", ""), haul] if x]
    tags = ""
    if job.get("added_by") == "MCS Auto":
        tags += "<span class='yb-tag'>MCS</span>"
    if job.get("install_dismantle"):
        tags += "<span class='yb-tag'>I/D</span>"
    who = _checked_by(dk, ji)
    state = (f"<span class='yb-ok'>{_yb_svg(YB_TICK, '#0a6a30', 12, 3)}{e(who)}</span>"
             if who else "<span class='yb-not'>Not Checked</span>")
    qs = _queries_for_job(dk, ji)
    if any(q.get("status") == "open" for _, q in qs):
        state += "<span class='yb-qopen'>Query Open</span>"
    elif any(q.get("status") == "answered" for _, q in qs):
        state += "<span class='yb-qans'>Query Answered</span>"
    border = "#e7a59c" if any(q.get("status") == "open" for _, q in qs) else "#dfe3df"
    return (
        f"<div class='yb-job' style='border-color:{border};'>"
        f"<div class='yb-job-top' style='color:{colour};'>"
        f"{_yb_svg(arrow, colour)}<span>{e(label)}</span>"
        f"<span class='yb-time'>{YB_CLOCK}Unknown</span></div>"
        f"<div class='yb-cust'>{e(job.get('customer') or 'No Customer')}</div>"
        + (f"<div class='yb-units'>{e(units)}</div>" if units else "")
        + (f"<div class='yb-meta'>{e(' · '.join(meta))}{tags}</div>" if meta or tags else "")
        + f"<div class='yb-state'>{state}</div></div>")


def _yb_day(day, w_idx):
    dk = fmt_key(day)
    day_jobs = jobs.get(dk, [])
    is_today = day == today
    is_bh = dk in bank_holidays
    n_q_open, _n_q_ans = _day_query_counts(dk)
    cls = "yb-day"
    if is_today:
        cls += " is-today"
    elif is_bh:
        cls += " is-bh"
    elif day.weekday() > 4:
        cls += " is-weekend"
    if n_q_open:
        cls += " has-query"
    head = (f"<div class='yb-day-name'>{day.strftime('%a')} "
            f"<span>{day.strftime('%-d %b')}</span></div>")
    if n_q_open:
        head += (f"<span class='yb-qcount' title='{n_q_open} Open "
                 f"Quer{'ies' if n_q_open > 1 else 'y'}'>{n_q_open}</span>")
    elif is_today:
        head += "<span class='yb-today'>Today</span>"
    counts = (f"<span>{_yb_svg(YB_TYPE['On Hire'][1], '#0d823b')}"
              f"{_yb_qty(day_jobs, 'On Hire')} Out</span>"
              f"<span>{_yb_svg(YB_TYPE['Off Hire'][1], '#a61b1b')}"
              f"{_yb_qty(day_jobs, 'Off Hire')} In</span>")
    extra = ""
    if is_bh:
        extra += f"<div class='yb-bh'>{_html_esc.escape(bank_holidays.get(dk, ''))}</div>"
    if day_jobs and day_jobs_fulfilment_complete(dk) and daily_checklist_done(dk):
        extra += "<div class='yb-dailys'>Dailys Complete</div>"
    sv_count = len(site_visits.get(dk, []))
    if sv_count:
        extra += (f"<div class='yb-sv'>{sv_count} Site Visit"
                  f"{'s' if sv_count > 1 else ''}</div>")
    st.markdown(
        f"<div class='{cls}'><div class='yb-day-head'><div class='yb-day-top'>{head}</div>"
        f"<div class='yb-counts'>{counts}</div>{extra}</div></div>",
        unsafe_allow_html=True)
    for ji, job in enumerate(day_jobs):
        with st.container(key=f"ybjob_{dk}_{ji}"):
            st.markdown(_yb_job_html(dk, ji, job), unsafe_allow_html=True)
            if st.button(f"Open {job.get('customer', 'Job')}", key=f"ybopen_{dk}_{ji}",
                         use_container_width=True):
                open_dialog(expand_date=dk, expand_idx=ji)
                st.rerun()
    if not day_jobs:
        st.markdown("<div class='yb-empty'>Nothing Booked Yet</div>",
                    unsafe_allow_html=True)
    name = day.strftime("%a")
    with st.container(key=f"ybadd_{dk}"):
        if st.button(f"+ Add {name}", key=f"day_{dk}", use_container_width=True):
            open_dialog(modal_date=dk, modal_edit_idx=None)
            st.rerun()
    if day_jobs or sv_count:
        with st.container(key=f"ybview_{dk}"):
            if st.button(f"Open {name}", key=f"dayview_{dk}", use_container_width=True,
                         help="Dailys, MCS check, site visits and every job for the day"):
                open_dialog(day_view_date=dk)
                st.rerun()


def _yb_week_label(ws):
    this_mon = get_monday(today)
    span = f"{ws.strftime('%-d')} to {(ws + timedelta(days=4)).strftime('%-d %b')}"
    if ws == this_mon:
        return f"This Week, {span}"
    if ws == this_mon + timedelta(weeks=1):
        return f"Next Week, {span}"
    if ws == this_mon - timedelta(weeks=1):
        return f"Last Week, {span}"
    return f"Week {week_num(ws)}, {span}"


sched_col, mat_col = st.columns([5, 1.4], gap="medium")

with sched_col:
    show_wkend = st.session_state.get("yb_weekend", False)
    for w in range(n_weeks):
        ws = start_date + timedelta(weeks=w)
        week_jobs = [j for d in range(7) for j in jobs.get(fmt_key(ws + timedelta(days=d)), [])]
        _on_u, _off_u, _on_t, _off_t, internal_dels, external_dels = week_unit_summary(ws)
        n_moves = sum(1 for j in week_jobs if j.get("type") == "Site Move")
        st.markdown(
            f"<div class='yb-week'><h3>{_yb_week_label(ws)}</h3><p>"
            f"<span><b class='g'>{_yb_qty(week_jobs, 'On Hire')}</b> Units Out</span>"
            f"<span><b class='r'>{_yb_qty(week_jobs, 'Off Hire')}</b> In</span>"
            f"<span><b class='b'>{n_moves}</b> Site Moves</span>"
            f"<span>Assets Moving: {internal_dels} Kensite Haulage, "
            f"{external_dels} External</span></p></div>",
            unsafe_allow_html=True)
        widths = [1, 1, 1, 1, 1, 0.16] + ([0.8, 0.8] if show_wkend else [])
        cols = st.columns(widths, gap="small")
        for d in range(5):
            with cols[d]:
                _yb_day(ws + timedelta(days=d), w)
        with cols[5]:
            with st.container(key=f"ybband_{w}"):
                if st.button("Hide Weekend" if show_wkend else "Sat and Sun",
                             key=f"ybband_btn_{w}", use_container_width=True,
                             help="Hide Saturday and Sunday" if show_wkend
                             else "Show Saturday and Sunday"):
                    st.session_state["yb_weekend"] = not show_wkend
                    st.rerun()
        if show_wkend:
            for d in (5, 6):
                with cols[d + 1]:
                    _yb_day(ws + timedelta(days=d), w)

with mat_col:
    _open_q = [(qid, q) for qid, q in queries.items() if q.get("status") == "open"]
    _open_q.sort(key=lambda x: x[1].get("date", ""))
    st.markdown(
        f"<div class='yb-side-head'>Queries"
        + (f"<span class='yb-qcount'>{len(_open_q)}</span>" if _open_q else "")
        + "</div>", unsafe_allow_html=True)
    if not _open_q:
        st.markdown("<div class='yb-empty'>No Open Queries</div>", unsafe_allow_html=True)
    for qid, q in _open_q[:8]:
        jref = q.get("job") or {}
        try:
            qday = datetime.strptime(q.get("date", ""), "%Y-%m-%d").strftime("%a %-d %b")
        except ValueError:
            qday = q.get("date", "")
        st.markdown(
            f"<div class='yb-q'><div class='yb-q-top'>{_html_esc.escape(qday)} · "
            f"{_html_esc.escape(str(q.get('raised_by', '')))} Is Asking</div>"
            f"<div class='yb-q-cust'>{_html_esc.escape(str(jref.get('customer', '')))}</div>"
            f"<div class='yb-q-text'>{_html_esc.escape(str(q.get('question', '')))}</div></div>",
            unsafe_allow_html=True)
        if st.button("Answer", key=f"ybq_{qid}", use_container_width=True):
            open_dialog(query_date=q.get("date"), query_idx=int(q.get("job_idx", 0)))
            st.rerun()
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    _badge_groups = {}
    for _r in materials.values():
        _badge_groups.setdefault(_mat_request_key(_r), []).append((0, _r))
    _pending_count = sum(1 for v in _badge_groups.values()
                         if _mat_group_state(v) == "pending")
    _badge = (f' <span style="background:#c0392b;color:white;'
              f'border-radius:10px;padding:1px 6px;font-size:10px;">'
              f'{_pending_count}</span>' if _pending_count else "")
    st.markdown(
        f"<div style='font-size:11px;font-weight:700;color:{K_GREY};"
        f"opacity:.7;letter-spacing:.07em;text-transform:uppercase;"
        f"padding-bottom:3px;text-align:center;'>Materials{_badge}</div>",
        unsafe_allow_html=True)

    st.markdown("<div class='ks-add-btn'>", unsafe_allow_html=True)
    if st.button("＋ Add Request", key="matadd_main", use_container_width=True):
        st.session_state["mat_add"]         = True
        st.session_state["any_dialog_open"] = True
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    mat_items = [(m, r) for m, r in materials.items()
                 if not _mat_received_expired(r)]
    mat_items.sort(key=lambda x: x[1].get("created_at", ""), reverse=True)
    _cnt_groups = {}
    for _m, _r in mat_items:
        _cnt_groups.setdefault(_mat_request_key(_r), []).append((_m, _r))
    _g_states  = [_mat_group_state(v) for v in _cnt_groups.values()]
    n_pending  = sum(1 for s in _g_states if s == "pending")
    n_ordered  = sum(1 for s in _g_states if s == "ordered")
    n_received = sum(1 for s in _g_states if s == "delivered")

    st.markdown(
        f"<div style='display:flex;gap:4px;margin:0 2px 5px;flex-wrap:wrap;"
        f"justify-content:center;'>"
        f"<span style='background:#fdecea;color:#7b1a1a;border-radius:4px;"
        f"padding:1px 6px;font-size:9.5px;font-weight:700;'>🔴 {n_pending} Requested</span>"
        f"<span style='background:#fff9e6;color:#7a5c00;border-radius:4px;"
        f"padding:1px 6px;font-size:9.5px;font-weight:700;'>🟡 {n_ordered} On Order</span>"
        f"<span style='background:{K_GREEN_PALE};color:{K_GREEN_DARK};border-radius:4px;"
        f"padding:1px 6px;font-size:9.5px;font-weight:700;'>🟢 {n_received} Delivered</span>"
        f"</div>",
        unsafe_allow_html=True)

    # fixed height: the panel scrolls internally once full, rather
    # than stretching the page
    mat_box = st.container(height=620)
    with mat_box:
        if not mat_items:
            st.markdown("<div class='day-empty' style='padding:8px;'>No requests</div>",
                        unsafe_allow_html=True)
        else:
            # One REQUEST = one group: requester + date header, with a
            # tree line branching down to each of its item pills.
            groups, order = {}, []
            for mid, req in mat_items:
                gkey = _mat_request_key(req)
                if gkey not in groups:
                    groups[gkey] = []
                    order.append(gkey)
                groups[gkey].append((mid, req))

            STATUS_COLS = {
                "pending":   ("#fdecea", "#7b1a1a", "#fbddd8"),
                "ordered":   ("#fff9e6", "#7a5c00", "#fff0c2"),
                "delivered": (K_GREEN_PALE, K_GREEN_DARK, "#d4ecdd"),
            }
            # One pill PER REQUEST: the button is the pill header, the
            # block beneath it holds a sub-pill per item and is styled
            # to read as the lower half of the same pill. Colour comes
            # from the whole request's state: green ONLY when every
            # line is ticked Delivered.
            btn_css = "<style>"
            for gkey in order:
                members = groups[gkey]
                g_status = _mat_group_state(members)
                c_bg, c_fg, c_hov = STATUS_COLS.get(
                    g_status, ("#f0f0f0", K_GREY, "#e6e6e6"))
                bkey = f"matreq_{members[0][0]}"
                btn_css += (
                    f".st-key-{bkey} button{{background:{c_bg} !important;"
                    f"color:{c_fg} !important;border:none !important;"
                    f"border-radius:8px 8px 0 0 !important;"
                    f"font-weight:700 !important;text-align:left "
                    f"!important;justify-content:flex-start !important;"
                    f"padding:6px 10px !important;}}"
                    f".st-key-{bkey} button:hover{{background:{c_hov} "
                    f"!important;color:{c_fg} !important;}}"
                    f".st-key-{bkey}{{margin-bottom:-14px !important;}}"
                )
            btn_css += "</style>"
            st.markdown(btn_css, unsafe_allow_html=True)

            for gkey in order:
                members = groups[gkey]
                head    = members[0][1]
                reqby   = head.get("requester", "")
                created = head.get("created_at", "")
                g_status = _mat_group_state(members)
                c_bg, c_fg, _hov = STATUS_COLS.get(
                    g_status, ("#f0f0f0", K_GREY, "#e6e6e6"))
                n_items = len(members)

                # pill header — clicking anywhere opens the request
                if st.button(f"{reqby}   ·   {created}   ·   "
                             f"{n_items} item{'s' if n_items != 1 else ''}",
                             key=f"matreq_{members[0][0]}",
                             use_container_width=True):
                    st.session_state["mat_view_id"]     = members[0][0]
                    st.session_state["any_dialog_open"] = True
                    st.rerun()

                # sub-pills, one per item: X while its PO awaits
                # approval, tick when approved, package when delivered
                subs = ""
                for _m, r in members:
                    note = r.get("notes", "")
                    state = _mat_line_state(r)
                    mark = MAT_LINE_MARK.get(state, "")
                    # po_html is HTML, not plain text, because the PO
                    # number is a link into Zahara. Everything drawn from
                    # the record is escaped as it goes in, so the caller
                    # below must NOT escape it a second time or the
                    # anchor would render as visible tags.
                    po_html = ""
                    if r.get("po_number"):
                        po_html = (_po_link_html(r)
                                   + (" · awaiting approval"
                                      if state == "awaiting" else ""))
                    elif state == "query":
                        po_html = _html_esc.escape(
                            'Ken asks: is this "'
                            + str((r.get("query") or {})
                                  .get("candidate_name", ""))[:45]
                            + '"? Open to answer')
                    elif state == "delivered" and (r.get("delivered_at")
                                                   or r.get("pod_received_at")):
                        po_html = _html_esc.escape(
                            f'Delivered '
                            f'{r.get("delivered_at") or r.get("pod_received_at")}')
                    subs += (
                        f'<div style="background:rgba(255,255,255,.6);'
                        f'border-radius:6px;padding:4px 8px;'
                        f'margin-top:4px;">'
                        f'<div style="font-size:11.5px;font-weight:700;'
                        f'color:{c_fg};line-height:1.3;">'
                        f'{mark + " " if mark else ""}'
                        f'{_html_esc.escape(str(r.get("item","")))}</div>'
                        + (f'<div style="font-size:10px;opacity:.75;'
                           f'color:{c_fg};line-height:1.3;">'
                           f'{po_html}</div>'
                           if po_html else "")
                        + (f'<div style="font-size:10px;opacity:.75;'
                           f'color:{c_fg};line-height:1.3;">'
                           f'{_html_esc.escape(str(note))}</div>'
                           if note else "")
                        + '</div>')
                st.markdown(
                    f'<div style="background:{c_bg};'
                    f'border-radius:0 0 8px 8px;padding:2px 8px 8px;'
                    f'margin-bottom:8px;">{subs}</div>',
                    unsafe_allow_html=True)


# ── SNAPSHOT ─────────────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("📸 Snapshot — export current view"):
    snap_html = f"""
    <div class="snap-outer">
      <div class="snap-header">
        <div class="snap-title">Kensite Prep Schedule</div>
        <div class="snap-period">{start_date.strftime('%d %b')} – {end_date.strftime('%d %b %Y')}
          &nbsp;·&nbsp; Generated {datetime.now().strftime('%d %b %Y %H:%M')}</div>
      </div>
    """
    for w in range(n_weeks):
        ws = start_date + timedelta(weeks=w)
        on_u, off_u, on_total, off_total, internal_dels, external_dels = week_unit_summary(ws)
        parts = []
        if on_u:
            parts.append("ON: " + ", ".join(f"{u}×{q}" for u, q in on_u.items()))
        if off_u:
            parts.append("OFF: " + ", ".join(f"{u}×{q}" for u, q in off_u.items()))
        wk_sum = " | ".join(parts)
        snap_html += (
            f'<div style="background:{K_GREEN_PALE};border:1px solid #c3dfc9;'
            f'border-top:none;padding:5px 10px;font-size:10px;font-weight:700;'
            f'color:{K_GREEN_DARK};">Week {week_num(ws)}'
            + (f' &nbsp;·&nbsp; {wk_sum}' if wk_sum else "")
            + '</div><div class="snap-grid">'
        )
        for d in range(7):
            day  = ws + timedelta(days=d)
            is_t = day == today
            snap_html += (
                f'<div class="snap-dh">'
                f'<div class="snap-dname">{day.strftime("%a")}</div>'
                f'<div class="snap-ddate {"snap-today" if is_t else ""}">'
                f'{day.strftime("%-d %b")}</div></div>'
            )
        for d in range(7):
            day = ws + timedelta(days=d)
            dk  = fmt_key(day)
            snap_html += "<div class='snap-body'>"
            for job in jobs.get(dk, []):
                bg, fg, _ = TYPE_STYLE[job["type"]]
                name  = job.get("customer", "")
                pc    = job.get("postcode", "")
                units = "  ".join(f'{u}×{q}' for u, q
                                  in job.get("units", {}).items() if q)
                type_tag = (f'<span style="font-size:8px;background:rgba(0,0,0,.1);'
                            f'border-radius:3px;padding:1px 4px;margin-right:3px;">'
                            f'{job["type"]}</span>')
                id_tag = ""
                if job.get("install_dismantle"):
                    id_tag = (f'<span style="font-size:8px;background:{K_GREEN};'
                              f'color:white;border-radius:3px;padding:1px 4px;">I/D</span>')
                snap_html += (
                    f'<div class="snap-chip" style="background:{bg};color:{fg}">'
                    f'<span class="snap-name">{name}</span>'
                    + (f'<span class="snap-sub">{pc}</span>' if pc else "")
                    + (f'<span class="snap-sub">{units}</span>' if units else "")
                    + f'<div style="margin-top:2px;">{type_tag}{id_tag}</div>'
                    + "</div>"
                )
            snap_html += "</div>"
        snap_html += "</div>"

    snap_html += (
        f'<div class="snap-footer">kensite.co.uk &nbsp;·&nbsp; 01942 878 747'
        f' &nbsp;·&nbsp; enquiries@kensite.co.uk</div></div>'
    )

    st.markdown(snap_html, unsafe_allow_html=True)

    full_html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<style>"
        "@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;600;800&display=swap');"
        f"body{{font-family:Figtree,Calibri,sans-serif;padding:20px;background:#fff;color:{K_GREY};}}"
        f".snap-outer{{max-width:1100px;margin:0 auto;}}"
        f".snap-header{{background:{K_GREEN};color:white;padding:14px 20px;border-radius:10px 10px 0 0;}}"
        f".snap-title{{font-size:18px;font-weight:800;}}"
        f".snap-period{{font-size:12px;opacity:.8;margin-top:2px;}}"
        f".snap-grid{{display:grid;grid-template-columns:repeat(7,1fr);"
        f"border:1px solid {K_LGREY};border-top:none;}}"
        f".snap-dh{{background:#f5f5f5;padding:6px 8px;border-right:1px solid {K_LGREY};"
        f"border-bottom:1px solid {K_LGREY};}}"
        f".snap-dname{{font-size:9px;font-weight:700;text-transform:uppercase;"
        f"color:{K_GREY};opacity:.5;letter-spacing:.06em;}}"
        f".snap-ddate{{font-size:14px;font-weight:800;color:{K_GREY};}}"
        f".snap-today{{color:{K_GREEN};}}"
        f".snap-body{{padding:5px;border-right:1px solid {K_LGREY};"
        f"border-bottom:1px solid {K_LGREY};min-height:80px;}}"
        f".snap-chip{{border-radius:4px;padding:3px 6px;margin-bottom:2px;"
        f"font-size:10px;line-height:1.3;}}"
        f".snap-name{{font-weight:700;display:block;}}"
        f".snap-sub{{font-size:9px;opacity:.7;}}"
        f".snap-footer{{background:#f9f9f9;padding:8px 16px;border:1px solid {K_LGREY};"
        f"border-top:none;border-radius:0 0 10px 10px;"
        f"font-size:10px;color:{K_GREY};opacity:.6;text-align:right;}}"
        "</style></head><body>"
        + snap_html +
        "</body></html>"
    )

    st.download_button(
        "⬇ Download Snapshot (HTML)",
        data=full_html,
        file_name=f"kensite_prep_schedule_{today}.html",
        mime="text/html",
        use_container_width=True
    )

