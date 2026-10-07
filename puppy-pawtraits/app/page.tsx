import { Commission } from '@/components/Commission';
import { Hero } from '@/components/Hero';
import { Nav } from '@/components/Nav';
import { Shop } from '@/components/Shop';
import { Work } from '@/components/Work';

export default function Home() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <Work />
        <Shop />
      </main>
      <Commission />
    </>
  );
}
