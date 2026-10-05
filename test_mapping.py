import json

def test_diagnostics():
    print("Simulating Frontend to Backend flow:")
    
    frontend_payload = {"linkedin_url": "https://linkedin.com/in/test"}
    print(f"Frontend sends: {frontend_payload}")
    
    # Backend simulation
    data = frontend_payload
    profile_url = (data.get("profile_url") or "").strip()
    if not profile_url:
        print("BACKEND ERROR: Backend expects 'profile_url' but received 'linkedin_url'!")
        print("Result: HTTP 400 'Please enter a valid LinkedIn profile URL.'")
    else:
        print("Backend successfully read URL.")
        
    print("\nSimulating Backend returning to Frontend:")
    extraction_data = {
        "tenant_id": "default",
        "profile": {"name": "Test"}
    }
    # app.py returns this:
    backend_response = {"success": True, "data": extraction_data}
    
    # Frontend receives this:
    js_data = backend_response
    print(f"Backend returns: {js_data}")
    currentExtractedData = js_data.get("profile")
    print(f"Frontend reads `data.profile` -> {currentExtractedData}")
    if currentExtractedData is None:
        print("FRONTEND ERROR: Frontend expects `data.profile` but backend returned data inside `data.data.profile`.")
        
if __name__ == "__main__":
    test_diagnostics()
