const ConflictSidebar = ({ trains, onApprove, onOverride, onMRDC }) => {
  const conflicts = trains.filter(t => t.status === 'delayed' || t.status === 'at_risk');

  return (
    <div style={{
      width: '280px',
      background: '#111',
      borderLeft: '1px solid #222',
      padding: '15px',
      overflowY: 'auto',
      height: '88vh'
    }}>
      <h3 style={{ margin: '0 0 15px 0', color: '#ff4444', fontSize: '14px' }}>
        ⚠️ CONFLICT ALERTS ({conflicts.length})
      </h3>

      {conflicts.length === 0 ? (
        <div style={{ color: '#00ff88', fontSize: '13px' }}>
          ✅ All trains running smoothly!
        </div>
      ) : (
        conflicts.map(train => (
          <div key={train.id} style={{
            background: '#1a1a1a',
            border: `1px solid ${train.status === 'delayed' ? '#ff4444' : '#ffaa00'}`,
            borderRadius: '8px',
            padding: '12px',
            marginBottom: '10px'
          }}>
            <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>
              🚂 {train.id}
            </div>
            <div style={{ fontSize: '12px', color: '#aaa', lineHeight: '1.6' }}>
              Status: <span style={{ color: train.status === 'delayed' ? '#ff4444' : '#ffaa00' }}>
                {train.status.toUpperCase()}
              </span><br/>
              Delay: {train.delay} mins<br/>
              Speed: {train.speed} km/h
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '10px' }}>
              
              <button onClick={() => onApprove && onApprove(train.id)}
                style={{
                  background: '#00ff88', color: '#000',
                  border: 'none', borderRadius: '5px',
                  padding: '5px', cursor: 'pointer',
                  fontWeight: 'bold', fontSize: '11px'
                }}>
                ✅ APPROVE AI
              </button>

              <button onClick={() => onOverride && onOverride(train.id)}
                style={{
                  background: '#ffaa00', color: '#000',
                  border: 'none', borderRadius: '5px',
                  padding: '5px', cursor: 'pointer',
                  fontWeight: 'bold', fontSize: '11px'
                }}>
                ✋ OVERRIDE MANUAL
              </button>

              <button onClick={() => onMRDC && onMRDC(train.id)}
                style={{
                  background: '#1a6fff', color: '#fff',
                  border: 'none', borderRadius: '5px',
                  padding: '5px', cursor: 'pointer',
                  fontWeight: 'bold', fontSize: '11px'
                }}>
                📡 MRDC SEND
              </button>

            </div>
          </div>
        ))
      )}
    </div>
  );
};

export default ConflictSidebar;
