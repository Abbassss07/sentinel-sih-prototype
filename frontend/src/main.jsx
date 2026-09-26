import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './SentinelApp'
import './sentinel.css'

createRoot(document.getElementById('root')).render(
  <StrictMode><App /></StrictMode>,
)
