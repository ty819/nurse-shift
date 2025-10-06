import './globals.css';

export const metadata = {
  title: '看護師シフト自動割当',
  description: 'OR-Toolsを使用した看護師シフト最適化システム',
};

export const viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}

