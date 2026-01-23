#!/bin/bash
# Run this script to apply database migrations to Railway

echo "🚀 Running database migrations on Railway..."
echo ""

# Check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Install it first:"
    echo "npm i -g @railway/cli"
    exit 1
fi

# Apply migration 001
echo "📦 Applying migration 001_add_parties.sql..."
railway run psql $DATABASE_URL -f backend/migrations/001_add_parties.sql

echo ""
echo "✅ Migration complete!"
echo ""
echo "🔍 Verifying campaign_id column exists..."
railway run psql $DATABASE_URL -c "SELECT column_name FROM information_schema.columns WHERE table_name='parties' AND column_name='campaign_id';"

echo ""
echo "✅ Done! Try connecting to the chat now."
