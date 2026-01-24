import argparse
import random
import compression.gzip  # New canonical import in Python 3.14
import sys
import xml.etree.ElementTree as ET
import re
import os
from FantasyNameGenerator.DnD import Aasimer, Dragonborn, Dwarf, Elf, Goblin, Gnome, Halfling, Human, Lizardfolk, Orc, Tiefling, Yuanti, HalfElf, HalfOrc

print("Town Population Parser - Worldographer Compatible")

# Global debug flag
debug = False

# Define age ranges for different races
ages = {
    "human": {"min": 16, "max": 80, "mean": 38, "std_dev": 12},
    "elf": {"min": 100, "max": 750, "mean": 300, "std_dev": 100},
    "dwarf": {"min": 40, "max": 350, "mean": 150, "std_dev": 50},
    "halfling": {"min": 20, "max": 150, "mean": 60, "std_dev": 20},
    "gnome": {"min": 40, "max": 500, "mean": 200, "std_dev": 70},
    "orc": {"min": 14, "max": 50, "mean": 25, "std_dev": 8},
    "goblin": {"min": 8, "max": 40, "mean": 20, "std_dev": 6},
    "dragonborn": {"min": 16, "max": 80, "mean": 40, "std_dev": 15},
    "tiefling": {"min": 16, "max": 80, "mean": 40, "std_dev": 15},
    "aasimar": {"min": 16, "max": 80, "mean": 40, "std_dev": 15},
    "yuan-ti": {"min": 16, "max": 80, "mean": 40, "std_dev": 15},
    "lizardfolk": {"min": 14, "max": 60, "mean": 30, "std_dev": 10},
    "half-elf": {"min": 20, "max": 180, "mean": 80, "std_dev": 30},
    "half-orc": {"min": 14, "max": 60, "mean": 30, "std_dev": 10},
}

# Define name generators for different races
names = {
    "human": Human,
    "elf": Elf,
    "dwarf": Dwarf,
    "halfling": Halfling,
    "gnome": Gnome,
    "orc": Orc,
    "goblin": Goblin,
    "dragonborn": Dragonborn,
    "tiefling": Tiefling,
    "aasimar": Aasimer,
    "yuan-ti": None,
    "lizardfolk": Lizardfolk,
    "half-elf": HalfElf,
    "half-orc": HalfOrc,
}

def generate_age(race,type="family"):
    # random.gauss returns a float; round it for an integer age
    if type == "family":
        age = round(random.gauss(ages[race]["mean"] * 2 / 3, ages[race]["std_dev"]))
    else:
        age = round(random.gauss(ages[race]["mean"], ages[race]["std_dev"]))
    # Keep age within realistic bounds
    base = 0 if type == "family" else ages[race]["min"]
    gen_age = max(base, min(ages[race]["max"], age))
    if debug:
        print(f"Generated age for {race} ({type}): {gen_age} ( {base}, {ages[race]["max"]}, {age})")

    return gen_age

def generate_names(race,orientation):
    if race not in { "yuan-ti", "changeling", "warforged", "bugbear" }:
        gen_name = names[race]().generate(gender=orientation.capitalize())
    elif race == "yuan-ti":
        gen_name = Lizardfolk().generate(gender=orientation.capitalize()) + " " + Yuanti().generate().capitalize()
    else:
        gen_name = "Nameless"

    if debug:
        print(f"Name generation for '{orientation}' '{race}' resulted in '{gen_name}'.")
    
    return gen_name

def read_wxx_file(file_path):
    uncompressed_text = ""

    try:
        # Open in 'rb' (read-binary) mode to handle the mixed data stream
        with compression.gzip.open(file_path, 'rb') as f:
            # Read in chunks (e.g., 1MB) to remain memory efficient
            while chunk := f.read(1024 * 1024):
                # Decode to UTF-8, but IGNORE bytes that are not valid text
                # This safely skips over binary data while keeping Unicode/ASCII
                decoded_part = chunk.decode('utf-8', errors='ignore')
                
                # Optional: Filter out non-printable characters (control codes)
                cleaned_part = "".join(c for c in decoded_part if c.isprintable() or c.isspace())
                
                uncompressed_text += cleaned_part

    except FileNotFoundError:
        print(f"Error: {file_path} not found.", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
    
    return uncompressed_text

def parse_wxx_file(town_data):
    # Wrap in root to handle multiple top-level elements (feature and note)
    raw_data = re.sub(r'<\?xml.*?\?>', '', town_data)
    raw_data = re.sub(r'\t\n', '\n', raw_data)
    raw_data = re.sub(r'\t', ',', raw_data)

    wrapped_xml = f"<root>{raw_data}</root>"
    root = ET.fromstring(wrapped_xml)
    for element in root.iter('*'):
        if 'tiles' in element.tag:
            map_hex_width = float(element.get('tilesWide'))
            map_hex_height = float(element.get('tilesHigh'))    

    # Dictionary to store {uuid: feature_label}
    town_buildings = {}

    # 1. Map features to their UUIDs
    for feature in root.iter('feature'):
        uuid = feature.get('uuid')
        feature_type = feature.get('type', '')
        feature_class = feature_type.split('/', 1)[0]

        if 'Battlemat'.casefold() in feature_class.casefold():
            continue  # Skip battlemat features

        # Extract label from the nested <label> tag
        label_el = feature.find('label')
        feat_loc = label_el.find('location')
        label_text = "".join(label_el.itertext()).strip().replace('\n', ' ').replace('  ',' ') if label_el is not None else None
        x_coord = float(feat_loc.get('x', 0)) / map_hex_width if feat_loc is not None else 0.0
        y_coord = float(feat_loc.get('y', 0)) / map_hex_height if feat_loc is not None else 0.0

        if label_text:
            town_buildings[uuid] = { "name" : label_text, "x": x_coord, "y": y_coord }
        else:
            if '/' in feature_type:
                # Splits at '/' and takes everything after it
                fallback_label = feature_type.split('/', 1)[1]
                fallback_label = fallback_label.split(' ', 2)[1] if ' ' in fallback_label else fallback_label
                town_buildings[uuid] = { "name" : fallback_label, "x": x_coord, "y": y_coord }

    # 2. Extract note data and link via 'parent' attribute
    for note in root.iter('note'):
        parent_uuid = note.get('parent')
        
        if parent_uuid is None or parent_uuid not in town_buildings:
            continue  # Skip notes without valid parent UUIDs

        # Get table text (contains the staff data)
        for table_data in note.iter('table'):
            if table_data is not None and table_data.text:
                table_key = table_data.get('key', 'unknown')
                if table_key is not None and table_data.text:
                    town_buildings[parent_uuid][table_key] = table_data.text.strip()

    return town_buildings

def display_population(town_population, options):
    replacements = options.replace if options.replace else []
    random_ages = options.ages if options.ages else False
    random_names = options.names if options.names else False

    populous = "\nTown Population Summary:\n"
    for uuid, building in town_population.items():
        if len(building) <= 3:
            continue  # Skip buildings without population data

        name = building.get("name", "Unknown")
        x = building.get("x", 0.0)
        y = building.get("y", 0.0)
        del building["name"]
        del building["x"]
        del building["y"]

        populous += f"Building: {name}\n"
        populous += f"  Location: ({x:.2f}, {y:.2f})" + "\n"

        for key in building:
            populous += f"  {key}:" + "\n"
            for row in building[key].split('\n'):
                row = row.replace('\t', ' ').replace('  ', ' ')
                cols = row.split(',')
                race = cols[1].strip().lower()
                race = race.replace('half-', '')
                for rep in replacements:
                    old, new = rep.split('=', 1)
                    race = race.replace(old, new)

                if race in ages.keys(): # dealing with a person entry (staff, resident, patron)
                    name = generate_names(race.lower(), cols[4]) if random_names else cols[0].strip()
                    
                    age = generate_age(race.lower(),key.lower()) if random_ages else int(cols[2].strip())

                    gender = cols[4] if random.randint(0,100) > 5 else "Fluid"
                    occupation = cols[5].replace('/ ','/').strip()
                    if key.lower() == "family":
                        occupation = occupation.replace('Member/','').strip()
                        if age <= ages[race]["min"]:
                            occupation = "Child"
                    notes = cols[6].strip() if age > 5 else "Toddler"
                    populous += f"\t{name:<25} {race.capitalize():<10} {age:<3} {gender:<6} {occupation:<25} {notes}" + "\n"
                else: # dealing with an item entry
                    item_row = re.sub('[ ,]*$', '', row)  # Remove trailing commas
                    cols = item_row.rsplit(',', maxsplit=2)
                    item_name = cols[0]
                    if len(cols) == 3:
                        if _m := re.match(r'^[\d ]+.p', cols[1]):
                            item_price = cols[1].replace(' ', '')
                            populous += f"\tQty: {cols[2]:<4} Price: {item_price:<8} {item_name}" + "\n"
                        if _m := re.match(r'^[\d ]+.p', cols[2]):
                            item_price = cols[2].replace(' ', '')
                            populous += f"\tQty: {cols[1]:<4} Price: {item_price:<8} {item_name}" + "\n"
                    elif len(cols) == 2:
                        if _m := re.match(r'^[\d ]+.p', cols[1]):
                            item_price = cols[1].replace(' ', '')
                            populous += f"\tQty: n/a  Price: {item_price:<8} {item_name}" + "\n"
                    else:
                        populous += f"\t{cols}" + "\n"
        populous += "-" * 40 + "\n"

    return populous

if __name__ == "__main__":
    try:
        # argparse in 3.14 includes native color support and typo suggestions
        parser = argparse.ArgumentParser(
            description="Read a gzipped file into a variable.",
            suggest_on_error=True  # Suggests correct flags if you type -g instead of -f
        )

        parser.add_argument(
            '--directory',
            help="Directory where town files are located (optional)"
        )
        parser.add_argument(
            '-f', '--file', 
            required=True, 
            help="Path to the compressed file to read"
        )
        parser.add_argument(
            '-o', '--output',
            help="Path to save the uncompressed output (optional)"
        )
        parser.add_argument(
            '-r', '--replace',
            action='append',
            help="Race/Species replacements in the format old=new"
        )
        parser.add_argument(
            '--names',
            action='store_true',
            help="Regenerate random names for residents"
        )
        parser.add_argument(
            '--ages',
            action='store_true',
            help="Regenerate random ages for residents"
        )
        parser.add_argument(
            '-s', '--seed',
            type=int,
            help="Seed for random number generator for reproducibility. If not provided, seed is based on filename."
        )
        parser.add_argument(
            '-d', '--debug',
            action='store_true',
            help="Enable debug output"
        )

        args = parser.parse_args()

        debug = args.debug

        if args.directory is not None:
            work_dir = args.directory
        elif os.environ.get('TOWN_DIR'):
            work_dir = os.environ.get('TOWN_DIR')
        else:
            work_dir = os.getcwd()
        
        town_file = os.path.join(work_dir, args.file)

        town = read_wxx_file(town_file)
        town_population = parse_wxx_file(town)

        if args.seed is not None:
            random.seed(args.seed)
            print(f"Using provided seed: {args.seed}")
        else:
            seed = args.file.split('/')[-1].split('.')[0].encode('utf-8')
            random.seed(int.from_bytes(seed, 'little'))
            print(f"Using seed based on filename: {int.from_bytes(seed, 'little')}")

        populous = display_population(town_population,args)
        if args.output:
            out_file = os.path.join(work_dir, args.output)
            with open(out_file, 'w', encoding='utf-8') as out_fd:
                out_fd.write(populous)
            print(f"Population summary written to {out_file}")
        else:
            print(populous)

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
