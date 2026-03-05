/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**.daft.ie' },
      { protocol: 'https', hostname: '**.myhome.ie' },
      { protocol: 'https', hostname: '**.propertypal.com' },
    ],
  },
};

module.exports = nextConfig;
