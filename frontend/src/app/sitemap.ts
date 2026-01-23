import { MetadataRoute } from 'next';

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://micro-alpha.com';

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  // Static pages
  const staticPages = [
    {
      url: BASE_URL,
      lastModified,
      changeFrequency: 'daily' as const,
      priority: 1,
    },
    {
      url: `${BASE_URL}/dashboard`,
      lastModified,
      changeFrequency: 'always' as const,
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/dashboard/feed`,
      lastModified,
      changeFrequency: 'always' as const,
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/dashboard/high-alpha`,
      lastModified,
      changeFrequency: 'always' as const,
      priority: 0.8,
    },
    {
      url: `${BASE_URL}/dashboard/search`,
      lastModified,
      changeFrequency: 'daily' as const,
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/dashboard/watchlist`,
      lastModified,
      changeFrequency: 'daily' as const,
      priority: 0.6,
    },
    {
      url: `${BASE_URL}/dashboard/alerts`,
      lastModified,
      changeFrequency: 'weekly' as const,
      priority: 0.5,
    },
    {
      url: `${BASE_URL}/auth/login`,
      lastModified,
      changeFrequency: 'monthly' as const,
      priority: 0.3,
    },
    {
      url: `${BASE_URL}/auth/register`,
      lastModified,
      changeFrequency: 'monthly' as const,
      priority: 0.3,
    },
  ];

  // In a real app, you would fetch popular tickers from the API
  // and generate dynamic pages for each ticker
  // For now, we'll include some common tickers as examples
  const popularTickers = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META'];

  const tickerPages = popularTickers.map((ticker) => ({
    url: `${BASE_URL}/dashboard/ticker/${ticker}`,
    lastModified,
    changeFrequency: 'hourly' as const,
    priority: 0.7,
  }));

  return [...staticPages, ...tickerPages];
}
