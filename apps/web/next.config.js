/** @type {import('next').NextConfig} */
const nextConfig = {
  // Imagem Docker pequena para o servidor (só o necessário em .next/standalone).
  output: 'standalone',
  serverExternalPackages: ["mongoose"],
  experimental: {
    // O disco desta máquina está quase cheio; sem esta cache o Turbopack não grava centenas de MB em .next/dev.
    turbopackFileSystemCacheForDev: false,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'images.pexels.com',
        port: '',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'res.cloudinary.com',
        port: '',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'd13552ljikd29j.cloudfront.net',
        port: '',
        pathname: '/**',
      },
    ],
  },
  // Rewrite para capturar todas as rotas Django
  async rewrites() {
    return [
      {
        source: '/api/django/:path*',
        destination: '/api/django',
      },
    ]
  },
}

module.exports = nextConfig