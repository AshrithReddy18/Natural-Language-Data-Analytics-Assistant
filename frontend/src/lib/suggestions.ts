import { Boxes, MapPin, TrendingUp, Users } from 'lucide-react'

// Example questions shown on the welcome screen and in search. Suggestions only: every answer
// still goes through the full pipeline.
export const SUGGESTIONS: { topic: string; icon: typeof TrendingUp; questions: string[] }[] = [
  {
    topic: 'Revenue trends',
    icon: TrendingUp,
    questions: ['Show monthly revenue for 2025.', 'Compare revenue between 2024 and 2025 by month.'],
  },
  {
    topic: 'Top customers',
    icon: Users,
    questions: [
      'What is the average order value by customer segment?',
      'What percentage of customers made more than one purchase?',
    ],
  },
  {
    topic: 'Product performance',
    icon: Boxes,
    questions: ['What were our top 5 products by revenue?', 'Which products have declining sales?'],
  },
  {
    topic: 'Regional sales',
    icon: MapPin,
    questions: ['Which city generated the highest sales?', 'How does revenue split across regions?'],
  },
]
