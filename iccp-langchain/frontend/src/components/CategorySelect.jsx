import { BookOpen, TrendingUp, Cpu, Coffee, Smartphone, Wallet, Sprout, Check } from 'lucide-react'

const CATEGORY_CONFIG = {
  finance: { icon: Wallet, color: 'text-emerald-600', bg: 'bg-emerald-100', border: 'border-emerald-300' },
  ai: { icon: Cpu, color: 'text-purple-600', bg: 'bg-purple-100', border: 'border-purple-300' },
  lifestyle: { icon: Coffee, color: 'text-orange-600', bg: 'bg-orange-100', border: 'border-orange-300' },
  tech: { icon: Smartphone, color: 'text-blue-600', bg: 'bg-blue-100', border: 'border-blue-300' },
  books: { icon: BookOpen, color: 'text-pink-600', bg: 'bg-pink-100', border: 'border-pink-300' },
  investment: { icon: TrendingUp, color: 'text-red-600', bg: 'bg-red-100', border: 'border-red-300' },
  growth: { icon: Sprout, color: 'text-green-600', bg: 'bg-green-100', border: 'border-green-300' },
}

function CategorySelect({ value, onChange, categories }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {categories.map((cat) => {
        const isSelected = value === cat.id
        const config = CATEGORY_CONFIG[cat.id] || CATEGORY_CONFIG.ai
        const Icon = config.icon

        return (
          <button
            key={cat.id}
            type="button"
            onClick={() => onChange(cat.id)}
            className={`relative group flex flex-col items-center justify-center p-4 rounded-lg border transition-all duration-200 ${
              isSelected
                ? `bg-card ${config.border} shadow-sm`
                : 'bg-card border hover:border-primary/30 hover:shadow-sm'
            }`}
          >
            {isSelected && (
              <div className="absolute top-2 right-2">
                <div className={`w-4 h-4 rounded-full ${config.bg} flex items-center justify-center`}>
                  <Check className={`w-2.5 h-2.5 ${config.color}`} />
                </div>
              </div>
            )}
            
            <div className={`p-3 rounded-full mb-3 transition-colors ${
              isSelected ? config.bg : 'bg-muted group-hover:bg-accent'
            }`}>
              <Icon className={`w-6 h-6 transition-colors ${
                isSelected ? config.color : 'text-muted-foreground group-hover:text-foreground'
              }`} />
            </div>
            
            <span className={`text-sm font-medium transition-colors ${
              isSelected ? 'text-foreground' : 'text-muted-foreground group-hover:text-foreground'
            }`}>
              {cat.name}
            </span>
          </button>
        )
      })}
    </div>
  )
}

export default CategorySelect
