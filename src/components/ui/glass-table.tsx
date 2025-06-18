// src/components/ui/glass-table.tsx
import { cn } from "@/lib/utils"
import { ReactNode } from "react"
import { Checkbox } from "@/components/ui/checkbox"

interface GlassTableProps {
  children: ReactNode
  className?: string
  variant?: "default" | "compact" | "comfortable"
}

interface GlassTableHeaderProps {
  children: ReactNode
  className?: string
  sticky?: boolean
}

interface GlassTableBodyProps {
  children: ReactNode
  className?: string
}

interface GlassTableRowProps {
  children: ReactNode
  className?: string
  onClick?: () => void
  isSelected?: boolean
  isHoverable?: boolean
  variant?: "default" | "compact"
}

interface GlassTableCellProps {
  children: ReactNode
  className?: string
  isHeader?: boolean
  align?: "left" | "center" | "right"
}

interface SelectableRowProps extends Omit<GlassTableRowProps, "isSelected"> {
  isSelected: boolean
  onSelectionChange: (selected: boolean) => void
  selectionDisabled?: boolean
}

export function GlassTable({
  children,
  className,
  variant = "default",
}: GlassTableProps) {
  const variantClasses = {
    default: "text-sm",
    compact: "text-xs",
    comfortable: "text-base",
  }

  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl glass border border-purple-muted/30",
        variantClasses[variant],
        className
      )}
    >
      <div className='overflow-x-auto'>
        <table className='w-full'>{children}</table>
      </div>
    </div>
  )
}

export function GlassTableHeader({
  children,
  className,
  sticky = false,
}: GlassTableHeaderProps) {
  return (
    <thead
      className={cn(
        "bg-black/20 border-b border-purple-muted/20",
        sticky && "sticky top-0 z-10",
        className
      )}
    >
      {children}
    </thead>
  )
}

export function GlassTableBody({ children, className }: GlassTableBodyProps) {
  return <tbody className={className}>{children}</tbody>
}

export function GlassTableRow({
  children,
  className,
  onClick,
  isSelected = false,
  isHoverable = true,
  variant = "default",
}: GlassTableRowProps) {
  return (
    <tr
      className={cn(
        "border-b border-purple-muted/10 transition-all duration-200",
        isHoverable &&
          "hover:bg-purple/5 hover:shadow-lg hover:shadow-purple/10",
        onClick && "cursor-pointer",
        isSelected && "bg-purple/10 border-purple/30",
        className
      )}
      onClick={onClick}
    >
      {children}
    </tr>
  )
}

export function SelectableTableRow({
  children,
  className,
  onClick,
  isSelected,
  onSelectionChange,
  selectionDisabled = false,
  isHoverable = true,
  variant = "default",
}: SelectableRowProps) {
  const handleRowClick = (e: React.MouseEvent) => {
    if (e.shiftKey && !selectionDisabled) {
      e.preventDefault()
      onSelectionChange(!isSelected)
    } else if (onClick) {
      onClick()
    }
  }

  const handleCheckboxChange = (checked: boolean) => {
    if (!selectionDisabled) {
      onSelectionChange(checked)
    }
  }

  return (
    <tr
      className={cn(
        "border-b border-purple-muted/10 transition-all duration-200",
        isHoverable &&
          "hover:bg-purple/5 hover:shadow-lg hover:shadow-purple/10",
        (onClick || !selectionDisabled) && "cursor-pointer",
        isSelected && "bg-cyan/10 border-cyan/30",
        className
      )}
      onClick={handleRowClick}
    >
      <td className='px-3 py-2 w-10'>
        <Checkbox
          checked={isSelected}
          onCheckedChange={handleCheckboxChange}
          disabled={selectionDisabled}
          className='border-cyan/50 data-[state=checked]:bg-cyan data-[state=checked]:border-cyan'
          onClick={(e) => e.stopPropagation()}
        />
      </td>
      {children}
    </tr>
  )
}

export function GlassTableCell({
  children,
  className,
  isHeader = false,
  align = "left",
}: GlassTableCellProps) {
  const alignClasses = {
    left: "text-left",
    center: "text-center",
    right: "text-right",
  }

  return (
    <td
      className={cn(
        "px-4 py-3 text-sm",
        isHeader ? "font-semibold text-pink" : "text-white",
        alignClasses[align],
        className
      )}
    >
      {children}
    </td>
  )
}

// For header cells specifically
export function GlassTableHeaderCell({
  children,
  className,
  align = "left",
}: GlassTableCellProps) {
  const alignClasses = {
    left: "text-left",
    center: "text-center",
    right: "text-right",
  }

  return (
    <th
      className={cn(
        "px-4 py-3 text-sm font-semibold text-pink tracking-wide",
        alignClasses[align],
        className
      )}
    >
      {children}
    </th>
  )
}
