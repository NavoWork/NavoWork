import { useEffect, useRef, useState, type RefObject } from 'react';

interface Props {
  label: string;
  controls: string;
  paneRef: RefObject<HTMLElement | null>;
  containerRef: RefObject<HTMLElement | null>;
  min: number;
  max: number;
  remainingMin: number;
  direction?: 1 | -1;
  onResize: (width: number) => void;
  onReset: () => void;
  onCollapse?: (expandedWidth: number) => void;
  className?: string;
}

/** A shared, keyboard-accessible divider for the two inquiry workspace boundaries. */
export function ResizeHandle({
  label,
  controls,
  paneRef,
  containerRef,
  min,
  max,
  remainingMin,
  direction = 1,
  onResize,
  onReset,
  onCollapse,
  className = '',
}: Props) {
  const drag = useRef<{ pointer: number; x: number; width: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const [geometry, setGeometry] = useState({ width: min, max });
  function bounds() {
    const available = containerRef.current?.clientWidth ?? min + max + 8;
    return { min, max: Math.max(min, Math.min(max, available - remainingMin - 8)) };
  }
  function resize(width: number) {
    const limit = bounds();
    onResize(Math.round(Math.max(limit.min, Math.min(limit.max, width))));
  }
  useEffect(() => {
    const measure = () =>
      setGeometry({
        width: Math.round(paneRef.current?.getBoundingClientRect().width || min),
        max: bounds().max,
      });
    const observer = new ResizeObserver(measure);
    if (containerRef.current) observer.observe(containerRef.current);
    if (paneRef.current) observer.observe(paneRef.current);
    measure();
    return () => observer.disconnect();
  }, [paneRef, containerRef, min, max, remainingMin]);
  useEffect(() => {
    if (!dragging) return;
    document.documentElement.classList.add('nw-resizing-panels');
    return () => document.documentElement.classList.remove('nw-resizing-panels');
  }, [dragging]);
  function finish() {
    drag.current = null;
    setDragging(false);
  }
  return (
    <div
      className={`nw-resize-handle ${dragging ? 'is-dragging' : ''} ${className}`}
      role="separator"
      tabIndex={0}
      aria-label={label}
      aria-controls={controls}
      aria-orientation="vertical"
      aria-valuemin={min}
      aria-valuemax={geometry.max}
      aria-valuenow={Math.max(min, Math.min(geometry.max, geometry.width))}
      aria-valuetext={`${geometry.width} 像素`}
      title={
        onCollapse
          ? '拖拽调整宽度，继续缩小可收起；双击恢复默认，方向键微调'
          : '拖拽调整宽度，双击恢复默认；方向键微调'
      }
      onPointerDown={(event) => {
        if (event.button !== 0 || !paneRef.current) return;
        event.preventDefault();
        event.currentTarget.focus();
        drag.current = {
          pointer: event.pointerId,
          x: event.clientX,
          width: paneRef.current.getBoundingClientRect().width,
        };
        event.currentTarget.setPointerCapture(event.pointerId);
        setDragging(true);
      }}
      onPointerMove={(event) => {
        if (drag.current?.pointer !== event.pointerId) return;
        const width = drag.current.width + (event.clientX - drag.current.x) * direction;
        // Keep a small buffer past the minimum so normal resizing does not hide the pane.
        if (onCollapse && width < min - 40) {
          const expandedWidth = drag.current.width;
          finish();
          if (event.currentTarget.hasPointerCapture(event.pointerId))
            event.currentTarget.releasePointerCapture(event.pointerId);
          onCollapse(expandedWidth);
        } else {
          resize(width);
        }
      }}
      onPointerUp={(event) => {
        if (drag.current?.pointer !== event.pointerId) return;
        if (event.currentTarget.hasPointerCapture(event.pointerId))
          event.currentTarget.releasePointerCapture(event.pointerId);
        finish();
      }}
      onPointerCancel={finish}
      onLostPointerCapture={finish}
      onDoubleClick={onReset}
      onKeyDown={(event) => {
        const width = paneRef.current?.getBoundingClientRect().width ?? geometry.width;
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
          event.preventDefault();
          resize(
            width + (event.key === 'ArrowRight' ? 1 : -1) * direction * (event.shiftKey ? 40 : 16),
          );
        } else if (event.key === 'Home' || event.key === 'End') {
          event.preventDefault();
          resize(event.key === 'Home' ? min : bounds().max);
        } else if (event.key === 'Enter') {
          event.preventDefault();
          onReset();
        }
      }}
    />
  );
}
