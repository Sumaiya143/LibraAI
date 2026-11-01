/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  images: { unoptimized: true },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Content-Security-Policy", value: "frame-ancestors 'none'; object-src 'none'; base-uri 'self'" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(self), geolocation=()" },
        { key: "X-DNS-Prefetch-Control", value: "on" },
      ],
    }];
  },
  async rewrites() {
    const backend = process.env.LIBRAAI_BACKEND_URL || "http://127.0.0.1:5000";
    return [{ source: "/backend/:path*", destination: `${backend}/:path*` }];
  }
};
export default nextConfig;
