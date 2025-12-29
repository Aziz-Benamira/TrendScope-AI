# TrendScope AI - Web Dashboard

Beautiful, modern web interface for TrendScope AI real-time movie trend analytics.

## Features

- 📊 **Real-time TrendScore Charts** - Visualize movie trends as they happen
- 🎬 **Top Trending Movies** - Live ranking of hottest movies
- 🤖 **ML Predictions** - See AI predictions vs actual trends
- 💭 **Sentiment Analysis** - Overall sentiment gauge
- 📈 **Live Statistics** - Key metrics updated in real-time
- 🎨 **Beautiful UI** - Modern gradient design with glassmorphism

## Quick Start

### Installation

```powershell
cd web-dashboard
npm install
```

### Run Development Server

```powershell
npm run dev
```

The dashboard will be available at: **http://localhost:3002**

### Build for Production

```powershell
npm run build
npm run preview
```

## Technology Stack

- **React 18** - UI framework
- **Vite** - Fast build tool
- **Tailwind CSS** - Styling
- **Recharts** - Data visualization
- **Lucide Icons** - Beautiful icons
- **Axios** - API calls

## API Integration

Currently uses mock data for development. To connect to real TrendScope API:

1. Update `API_BASE_URL` in `src/api.js`
2. Ensure backend API is running
3. Data will automatically switch from mock to real

## Features Breakdown

### Dashboard Sections

1. **Header** - Branding and live status indicator
2. **Stats Cards** - 4 key metrics (movies tracked, avg score, predictions, accuracy)
3. **Top Trending** - Scrollable list of trending movies with scores
4. **TrendScore Timeline** - Multi-line chart showing trends over time
5. **ML Predictions** - Scatter plot comparing predictions vs actual
6. **Sentiment Gauge** - Visual representation of overall sentiment

### Auto-Refresh

Data refreshes every 30 seconds to show latest trends.

## Customization

### Colors

Edit `tailwind.config.js` to change theme colors:

```js
colors: {
  primary: '#6366f1',    // Indigo
  secondary: '#8b5cf6',  // Purple
  accent: '#ec4899',     // Pink
}
```

### Refresh Rate

Change in `src/App.jsx`:

```js
const interval = setInterval(loadData, 30000); // 30 seconds
```

## Screenshots

The dashboard features:
- Gradient purple background
- Glassmorphism cards
- Smooth animations
- Responsive design
- Real-time updates

## Next Steps

Connect to the backend API by creating API endpoints that serve:
- `/api/trending` - Top trending movies
- `/api/predictions` - ML predictions
- `/api/stats` - System statistics
