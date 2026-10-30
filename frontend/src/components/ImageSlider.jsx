import React, { useState, useRef, useEffect } from 'react';
import { Columns, SplitSquareVertical, Layers } from 'lucide-react';
import AuthenticatedImage from './AuthenticatedImage';

const ImageSlider = ({
  beforeImage,
  afterImage,
  heatmapImage,
  beforeLabel = 'Baseline Image',
  afterLabel = 'Newer Snapshot',
  heatmapLabel = 'Highlighted differences'
}) => {
  const [sliderPos, setSliderPos] = useState(50); // percentage 0 - 100
  const [isDragging, setIsDragging] = useState(false);
  const [viewMode, setViewMode] = useState('split'); // 'split' or 'side-by-side'
  const [showHeatmap, setShowHeatmap] = useState(false);
  const containerRef = useRef(null);

  const activeAfterImage = showHeatmap && heatmapImage ? heatmapImage : afterImage;
  const activeAfterLabel = showHeatmap && heatmapImage ? heatmapLabel : afterLabel;

  const handleMouseDown = () => setIsDragging(true);
  const handleMouseMove = (e) => {
    if (!isDragging || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const width = rect.width;
    const clampedPos = Math.max(0, Math.min(100, (x / width) * 100));
    setSliderPos(clampedPos);
  };

  const handleTouchMove = (e) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const touch = e.touches[0];
    const x = touch.clientX - rect.left;
    const width = rect.width;
    const clampedPos = Math.max(0, Math.min(100, (x / width) * 100));
    setSliderPos(clampedPos);
  };

  useEffect(() => {
    const handleGlobalMouseUp = () => setIsDragging(false);
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => window.removeEventListener('mouseup', handleGlobalMouseUp);
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', width: '100%' }}>
      {/* View Mode Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setViewMode('split')}
            className={`btn btn-sm ${viewMode === 'split' ? 'btn-primary' : 'btn-secondary'}`}
          >
            <SplitSquareVertical size={14} />
            <span>Slide to compare</span>
          </button>
          <button
            onClick={() => setViewMode('side-by-side')}
            className={`btn btn-sm ${viewMode === 'side-by-side' ? 'btn-primary' : 'btn-secondary'}`}
          >
            <Columns size={14} />
            <span>View both photos</span>
          </button>
        </div>

        {heatmapImage && (
          <button
            onClick={() => setShowHeatmap(!showHeatmap)}
            className={`btn btn-sm ${showHeatmap ? 'btn-primary' : 'btn-secondary'}`}
            style={{ background: showHeatmap ? 'linear-gradient(135deg, #d97706 0%, #b45309 100%)' : undefined }}
          >
            <Layers size={14} />
            <span>{showHeatmap ? 'Hide highlighted areas' : 'Highlight different areas'}</span>
          </button>
        )}
      </div>
      <p className="comparison-slider-help">
        {viewMode === 'split'
          ? 'Drag the middle handle left or right to reveal each photo.'
          : 'The earlier photo is on the left; the later photo is on the right.'}
        {heatmapImage && ' Highlighted areas show where the computer noticed visual differences, not confirmed changes.'}
      </p>

      {/* Render Mode: Interactive Split Slider */}
      {viewMode === 'split' ? (
        <div
          ref={containerRef}
          className="comparison-slider-container"
          onMouseMove={handleMouseMove}
          onTouchMove={handleTouchMove}
          style={{ width: '100%', aspectRatio: '1 / 1', position: 'relative', cursor: isDragging ? 'ew-resize' : 'default' }}
        >
          {/* Baseline Base Image */}
          <AuthenticatedImage
            src={beforeImage}
            alt={beforeLabel}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
          <div
            style={{
              position: 'absolute',
              top: '12px',
              left: '12px',
              padding: '4px 10px',
              background: 'rgba(0, 0, 0, 0.75)',
              color: '#6ee7a8',
              borderRadius: '6px',
              fontSize: '0.78rem',
              fontWeight: 600,
              backdropFilter: 'blur(4px)',
            }}
          >
            {beforeLabel}
          </div>

          {/* Newer/Comparison Image Overlaid on the Right */}
          <div
            className="comparison-overlay-image"
            style={{
              width: `${100 - sliderPos}%`,
              left: `${sliderPos}%`,
              right: 0,
            }}
          >
            <AuthenticatedImage
              src={activeAfterImage}
              alt={activeAfterLabel}
              style={{
                width: containerRef.current ? `${containerRef.current.clientWidth}px` : '100%',
                maxWidth: 'none',
                height: '100%',
                objectFit: 'cover',
                transform: `translateX(-${sliderPos}%)`,
              }}
            />
          </div>

          <div
            style={{
              position: 'absolute',
              top: '12px',
              right: '12px',
              padding: '4px 10px',
              background: 'rgba(0, 0, 0, 0.75)',
              color: showHeatmap ? '#f59e0b' : '#34d399',
              borderRadius: '6px',
              fontSize: '0.78rem',
              fontWeight: 600,
              backdropFilter: 'blur(4px)',
              pointerEvents: 'none',
            }}
          >
            {activeAfterLabel}
          </div>

          {/* Draggable Divider Bar */}
          <div
            className="comparison-divider-line"
            style={{ left: `${sliderPos}%` }}
            onMouseDown={handleMouseDown}
            onTouchStart={() => setIsDragging(true)}
          >
            <div className="comparison-handle">
              <SplitSquareVertical size={16} />
            </div>
          </div>
        </div>
      ) : (
        /* Render Mode: Side-by-Side */
        <div className="comparison-side-by-side">
          <div className="glass-panel" style={{ overflow: 'hidden', padding: 0 }}>
            <div className="comparison-image-label">
              {beforeLabel}
            </div>
            <AuthenticatedImage src={beforeImage} alt={beforeLabel} style={{ width: '100%', aspectRatio: '1/1', objectFit: 'cover' }} />
          </div>

          <div className="glass-panel" style={{ overflow: 'hidden', padding: 0 }}>
            <div className="comparison-image-label">
              {activeAfterLabel}
            </div>
            <AuthenticatedImage src={activeAfterImage} alt={activeAfterLabel} style={{ width: '100%', aspectRatio: '1/1', objectFit: 'cover' }} />
          </div>
        </div>
      )}
    </div>
  );
};

export default ImageSlider;
