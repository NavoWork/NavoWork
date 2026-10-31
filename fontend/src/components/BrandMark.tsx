/** Approved v4 SVG assets. CSS switches the variants alongside the current theme. */
export function BrandMark({ className = '' }: { className?: string }) {
  return (
    <span className={`brand-mark ${className}`} aria-hidden="true">
      <img
        className="navo-logo-light"
        src="/brand/navowork-icon-light.svg"
        width="44"
        height="44"
        alt=""
      />
      <img
        className="navo-logo-dark"
        src="/brand/navowork-icon-dark.svg"
        width="44"
        height="44"
        alt=""
      />
    </span>
  );
}
