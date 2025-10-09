#!/bin/sh
# Generate runtime configuration file for the frontend

cat > /usr/share/nginx/html/config.js <<EOF
window.ENV = {
  VITE_API_BASE: "${VITE_API_BASE:-}",
  VITE_REALTIME_API_BASE: "${VITE_REALTIME_API_BASE:-}"
};
EOF

echo "Generated config.js with VITE_API_BASE=${VITE_API_BASE:-}"

# Start nginx
exec nginx -g 'daemon off;'
