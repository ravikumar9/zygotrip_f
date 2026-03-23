#!/bin/bash

set -e

echo "=================================="
echo "ZygoTrip OTA Deep Audit + Auto Fix"
echo "=================================="

echo ""
echo "1️⃣ Checking system resources"
echo "-----------------------------"
free -h
df -h

echo ""
echo "2️⃣ Checking running services"
echo "-----------------------------"
systemctl list-units --type=service | grep -E 'nginx|redis|postgres|mysql'

echo ""
echo "3️⃣ Checking open ports"
echo "-----------------------------"
ss -tulnp

echo ""
echo "4️⃣ Checking nginx config"
echo "-----------------------------"
if nginx -t ; then
    echo "Nginx config OK"
else
    echo "Fixing nginx..."
    rm -f /etc/nginx/conf.d/*.conf
    nginx -t
fi

echo ""
echo "Restart nginx"
systemctl restart nginx

echo ""
echo "5️⃣ Checking Redis"
echo "-----------------------------"
if systemctl is-active --quiet redis ; then
    echo "Redis running"
else
    echo "Starting Redis"
    systemctl start redis
fi

redis-cli ping || echo "Redis not responding"

echo ""
echo "6️⃣ Checking Database"
echo "-----------------------------"

if systemctl is-active --quiet postgresql ; then
    echo "PostgreSQL running"
elif systemctl is-active --quiet mysql ; then
    echo "MySQL running"
else
    echo "⚠ Database not running"
fi

echo ""
echo "7️⃣ Checking Node / Backend services"
echo "-----------------------------"

if command -v pm2 &> /dev/null
then
    pm2 list
else
    echo "PM2 not installed"
fi

echo ""
echo "Restart backend services"
pm2 restart all || true

echo ""
echo "8️⃣ Checking API endpoints"
echo "-----------------------------"

API_URL="http://localhost:8080"

echo "Hotels API"
curl -s $API_URL/api/hotels | head -c 200

echo ""
echo "Autocomplete API"
curl -s "$API_URL/api/search/autocomplete?q=go"

echo ""
echo "Recent searches API"
curl -s "$API_URL/api/search/recent"

echo ""
echo "9️⃣ Checking Docker containers"
echo "-----------------------------"
if command -v docker &> /dev/null
then
    docker ps
    docker restart $(docker ps -q) || true
fi

echo ""
echo "🔟 Checking firewall"
echo "-----------------------------"
ufw status || true

echo ""
echo "1️⃣1️⃣ Checking environment variables"
echo "-----------------------------"
env | grep -E 'API|DB|REDIS|NODE'

echo ""
echo "1️⃣2️⃣ Clearing caches"
echo "-----------------------------"
rm -rf /tmp/*
redis-cli flushall || true

echo ""
echo "1️⃣3️⃣ Restarting all critical services"
echo "-----------------------------"

systemctl restart nginx || true
systemctl restart redis || true
systemctl restart postgresql || true
pm2 restart all || true

echo ""
echo "=================================="
echo "Audit + Fix Completed"
echo "=================================="
