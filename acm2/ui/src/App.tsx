import { Routes, Route } from 'react-router-dom'
import Layout from './pages/Layout'
import Dashboard from './pages/Dashboard'
import ExecutionHistory from './pages/ExecutionHistory'
import ExecutionDetail from './pages/ExecutionDetail'
import Execute from './pages/Execute'
import Settings from './pages/Settings'
import Configure from './pages/Configure'
import Evaluation from './pages/Evaluation'
import ContentLibrary from './pages/ContentLibrary'
import GitHubConnections from './pages/GitHubConnections'
import { NotificationContainer } from './components/ui/notification'

function App() {
  return (
    <>
      <NotificationContainer />
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="configure" element={<Configure />} />
          <Route path="content" element={<ContentLibrary />} />
          <Route path="execute" element={<Execute />} />
          <Route path="execute/:runId" element={<Execute />} />
          <Route path="history" element={<ExecutionHistory />} />
          <Route path="history/:id" element={<ExecutionDetail />} />
          <Route path="evaluation" element={<Evaluation />} />
          <Route path="settings" element={<Settings />} />
          <Route path="github" element={<GitHubConnections />} />
        </Route>
      </Routes>
    </>
  )
}

export default App
