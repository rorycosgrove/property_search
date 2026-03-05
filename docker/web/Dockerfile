FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY web/package.json web/package-lock.json* ./
RUN npm install

# Copy source
COPY web/ .

# Build for production
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
