const Logo = () => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      
      <img 
        src="/RAILDRISHTI.png"
        alt="RailDrishti Logo"
        style={{
          width: '52px',
          height: '52px',
          borderRadius: '50%',
          objectFit: 'cover',
          boxShadow: '0 0 12px rgba(204,0,0,0.6)',
        }}
      />

      <h1 style={{
        margin: 0,
        fontSize: '22px',
        fontWeight: '900',
        color: '#ffffff',
        letterSpacing: '1px'
      }}>
        RailDrishti
      </h1>

    </div>
  );
};

export default Logo;