import nextra from 'nextra';

const withNextra = nextra({
  theme: 'nextra-theme-docs',
  themeConfig: './theme.config.tsx',
});

export default withNextra({
  output: 'export',
  images: {
    unoptimized: true,
  },
  basePath: process.env.NODE_ENV === 'production' ? '/copinance-os' : '',
  assetPrefix: process.env.NODE_ENV === 'production' ? '/copinance-os' : '',
  // Next 15 page-type validator conflicts with Nextra _meta config objects
  typescript: { ignoreBuildErrors: true },
});
