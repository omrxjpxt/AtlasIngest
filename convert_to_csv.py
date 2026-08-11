import json
import csv
import os

def jsonl_to_csv(jsonl_path, csv_path):
    if not os.path.exists(jsonl_path):
        print(f"File not found: {jsonl_path}")
        return
        
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    if not lines:
        print(f"Empty file: {jsonl_path}")
        return
        
    # parse all records
    records = [json.loads(line) for line in lines]
    
    # Flatten JSON logic
    def flatten_dict(d, parent_key='', sep='_'):
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    flat_records = [flatten_dict(r) for r in records]
    
    # Get all unique headers
    headers = set()
    for fr in flat_records:
        headers.update(fr.keys())
    headers = sorted(list(headers))
    
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(flat_records)
        
    print(f"Successfully converted {jsonl_path} to {csv_path} ({len(flat_records)} rows)")

def main():
    base_dir = "data"
    files = [
        "research_papers.jsonl",
        "startups.jsonl",
        "products.jsonl",
        "jobs.jsonl",
        "news.jsonl"
    ]
    
    for f in files:
        jsonl_path = os.path.join(base_dir, f)
        csv_path = os.path.join(base_dir, f.replace(".jsonl", ".csv"))
        if os.path.exists(jsonl_path):
            jsonl_to_csv(jsonl_path, csv_path)

if __name__ == "__main__":
    main()
