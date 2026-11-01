# Authored by Abdullah on 31/10/2026
from generation_engine.models import DemoRequest
from generation_engine.orchestrator import run_pipeline


# Create a sample request.
request = DemoRequest(
    prompt="Write a scene where Princess Amina defends her castle.",
    mode="verified",
    max_repair_attempts=3,
)

# Run the workflow.
result = run_pipeline(request)

# Display the result.
print("Status:", result.status)
print("Initial scene:", result.initial_scene.text)
print("Final scene:", result.final_scene.text)
print("Repair attempts:", result.repair_attempts)

# Confirm that the repair worked.
assert result.status == "verified"
assert result.repair_attempts == 1
assert "magical firestorm" in result.initial_scene.text
assert "magical firestorm" not in result.final_scene.text

print("Test passed.")