import { Play, Clock, CheckCircle, AlertCircle } from 'lucide-react'

// Placeholder stats - will be replaced with real data from API
const stats = [
  { name: 'Total Runs', value: '0', icon: Play, color: 'text-blue-500' },
  { name: 'Running', value: '0', icon: Clock, color: 'text-yellow-500' },
  { name: 'Completed', value: '0', icon: CheckCircle, color: 'text-green-500' },
  { name: 'Failed', value: '0', icon: AlertCircle, color: 'text-red-500' },
]

export default function Dashboard() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <div
            key={stat.name}
            className="bg-card border rounded-lg p-4 flex items-center gap-4"
          >
            <div className={`p-2 rounded-full bg-muted ${stat.color}`}>
              <stat.icon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{stat.name}</p>
              <p className="text-2xl font-bold text-foreground">{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Runs */}
      <div className="bg-card border rounded-lg">
        <div className="px-4 py-3 border-b">
          <h2 className="font-semibold text-foreground">Recent Runs</h2>
        </div>
        <div className="p-8 text-center text-muted-foreground">
          <Play className="h-12 w-12 mx-auto mb-3 opacity-50" />
          <p>No runs yet</p>
          <p className="text-sm mt-1">
            Go to the Build Preset page to start a new run.
          </p>
        </div>
      </div>
    </div>
  )
}
