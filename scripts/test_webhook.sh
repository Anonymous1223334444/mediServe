#!/bin/bash
# test_webhook.sh - Tester le webhook de différentes façons

echo "🔍 TEST DU WEBHOOK WHATSAPP"
echo "=========================="

# URL de base
BASE_URL="https://orca-eternal-specially.ngrok-free.app"

echo -e "\n1️⃣ Test GET (navigateur):"
echo "Commande: curl -X GET $BASE_URL/api/webhook/twilio/"
curl -X GET "$BASE_URL/api/webhook/twilio/"

echo -e "\n\n2️⃣ Test POST local:"
echo "Commande: curl -X POST http://localhost:8000/api/webhook/twilio/ ..."
curl -X POST http://localhost:8000/api/webhook/twilio/ \
  -d "From=whatsapp:+221778828376" \
  -d "Body=Test local" \
  -d "To=whatsapp:+16065955879"

echo -e "\n\n3️⃣ Test POST via ngrok:"
echo "Commande: curl -X POST $BASE_URL/api/webhook/twilio/ ..."
curl -X POST "$BASE_URL/api/webhook/twilio/" \
  -d "From=whatsapp:+221778828376" \
  -d "Body=Test ngrok" \
  -d "To=whatsapp:+16065955879"

echo -e "\n\n4️⃣ Test avec headers Twilio:"
curl -X POST "$BASE_URL/api/webhook/twilio/" \
  -H "X-Twilio-Signature: test" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+221778828376" \
  -d "Body=Test avec headers" \
  -d "To=whatsapp:+16065955879" \
  -d "MessageSid=SM1234567890"

echo -e "\n\n✅ Tests terminés"