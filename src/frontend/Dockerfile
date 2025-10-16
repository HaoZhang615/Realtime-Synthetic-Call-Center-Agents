###############################################
# Build stage for React app                  #
###############################################

FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy React app source
COPY . ./

# Build the React app
RUN npm run build

###############################################
# Production stage with nginx                #
###############################################

FROM nginx:alpine

# Copy built React app from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy entrypoint script and ensure Unix line endings
COPY entrypoint.sh /entrypoint.sh
RUN dos2unix /entrypoint.sh || sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Expose port 80
EXPOSE 80

# Use entrypoint to generate runtime config
ENTRYPOINT ["/entrypoint.sh"]