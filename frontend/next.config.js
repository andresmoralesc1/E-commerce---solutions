/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  experimental: {
    serverActions: { bodySizeLimit: "2mb" },
  },
};

const withNextIntl = require("next-intl/plugin")("./i18n.ts");
module.exports = withNextIntl(nextConfig);