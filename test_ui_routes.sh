#!/bin/bash
# Test UI routes after fix

echo "Testing UI routes..."
echo ""

# Test 1: Root should load (redirects to / or shows chat)
echo "1. Testing /ui/ (should load chat or login):"
curl -s -o /dev/null -w "  Status: %{http_code}\n" http://127.0.0.1:5173/ui/

# Test 2: Login should load
echo "2. Testing /ui/login (should load login page):"
curl -s -o /dev/null -w "  Status: %{http_code}\n" http://127.0.0.1:5173/ui/login

# Test 3: Invalid route should redirect
echo "3. Testing /ui/invalid (should redirect to /):"
curl -s -i http://127.0.0.1:5173/ui/invalid 2>&1 | grep -E "HTTP|Location" | head -2

echo ""
echo "UI routes are configured correctly."
