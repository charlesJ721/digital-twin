import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const notes = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/notes' }),
  schema: z.object({
    title: z.string().optional(),
    创建: z.string().optional(),
    'dg-publish': z.boolean().optional().default(true),
    layer: z.enum(['范式层', '架构层', '手段层']).optional(),
    tags: z.array(z.string()).optional().default([]),
    stage: z.string().optional(),
    category: z.string().optional(),
  }),
});

export const collections = { notes };
