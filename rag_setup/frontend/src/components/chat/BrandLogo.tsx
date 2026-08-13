interface BrandLogoProps {
  size?: "xs" | "sm" | "md" | "lg"
  className?: string
}

const sizeClasses = {
  xs: "size-8 rounded-xl",
  sm: "size-10 rounded-2xl",
  md: "size-12 rounded-2xl",
  lg: "size-20 rounded-[1.6rem]",
}

const iconClasses = {
  xs: "size-5",
  sm: "size-6",
  md: "size-7",
  lg: "size-11",
}

export function BrandLogo({
  size = "md",
  className = "",
}: BrandLogoProps) {
  return (
    <span
      className={`brand-gradient relative inline-flex shrink-0 items-center justify-center overflow-hidden text-white shadow-[0_10px_25px_rgba(20,72,100,0.22)] ${sizeClasses[size]} ${className}`}
      aria-hidden="true"
    >
      <span className="absolute inset-0 bg-[radial-gradient(circle_at_24%_15%,rgba(255,255,255,0.28),transparent_36%)]" />

      <svg
        viewBox="0 0 48 48"
        fill="none"
        className={`relative ${iconClasses[size]}`}
      >
        <path
          d="M24 5.5 38 11v10.6c0 9.1-5.5 16.6-14 20.9-8.5-4.3-14-11.8-14-20.9V11L24 5.5Z"
          stroke="currentColor"
          strokeWidth="2.8"
          strokeLinejoin="round"
        />
        <path
          d="M15.5 24h5.2l3.1-6 4.3 12 3.1-6H35"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="15.5" cy="24" r="1.8" fill="currentColor" />
        <circle cx="35" cy="24" r="1.8" fill="currentColor" />
      </svg>
    </span>
  )
}
