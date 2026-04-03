import MapView from './components/MapView';

function App() {
  return (
    <div>
      <h1 style={{ color: 'white', position: 'absolute', zIndex: 1, padding: '10px' }}>
        🚂 RailDrishti
      </h1>
      <MapView />
    </div>
  );
}

export default App;
