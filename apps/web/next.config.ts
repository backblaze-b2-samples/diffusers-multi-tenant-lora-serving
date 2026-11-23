import type { NextConfig } from "next";

// Allow `next/image` to optimize remote previews coming from Backblaze B2.
// Presigned download URLs use the bucket-specific S3 hostname pattern:
//   <bucket>.s3.<region>.backblazeb2.com    (path-style and virtual-host)
//   s3.<region>.backblazeb2.com             (path-style)
// One wildcard covers every region + bucket, so this config drops in
// without per-deployment tweaks.
const nextConfig: NextConfig = {
  transpilePackages: ["@diffusers-multi-tenant-lora-serving/shared"],
  // Playwright drives the dev server at 127.0.0.1 (see playwright.config.ts);
  // Next only serves its dev resources to localhost unless the origin is listed,
  // and without them the page never hydrates.
  allowedDevOrigins: ["127.0.0.1"],
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**.backblazeb2.com",
      },
    ],
  },
};

export default nextConfig;
