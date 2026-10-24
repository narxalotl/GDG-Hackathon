from report.py import build_report

# Sample dummy data to simulate Person 1 and Person 2 output
room_name = "Living Room"
confirmed_items = [
    {
        "category": "damage",
        "location": "North Wall",
        "description": "Large hole in drywall behind door",
        "severity": "major",
        "confidence": "high"
    }
]

# Pass paths to test images or placeholder files
output = build_report(
    room_name=room_name,
    confirmed_items=confirmed_items,
    before_path="before.jpg",  # Ensure you have two sample JPG images in your folder
    after_path="after.jpg",
    output_path="test_evidence_report.pdf"
)

print(f"Report generated successfully: {output}")