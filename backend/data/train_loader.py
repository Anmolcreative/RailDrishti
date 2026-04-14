import json

def load_trains():
    all_trains = []
    files = [
        ("backend/data/EXP-TRAINS.json", "MAIL_EXPRESS"),
        ("backend/data/SF-TRAINS.json", "SUPERFAST"),
        ("backend/data/PASS-TRAINS.json", "PASSENGER"),
    ]
    for path, train_type in files:
        with open(path) as f:
            data = json.load(f)
        for train in data:
            stops = [s["stationName"] for s in train.get("trainRoute", [])]
            all_trains.append({
                "train_id": str(train.get("trainNumber", "")),
                "name": train.get("trainName", ""),
                "type": train_type,
                "stops": stops
            })
    return all_trains

if __name__ == "__main__":
    trains = load_trains()
    print("Total trains loaded:", len(trains))
    print("Sample:", trains[0])
    with open("backend/data/trains.json", "w") as f:
        json.dump(trains, f, indent=2)
    print("Saved to backend/data/trains.json")