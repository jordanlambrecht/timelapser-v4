// src/components/ui/combobox.tsx
"use client"

import * as React from "react"
import { CheckIcon, ChevronsUpDownIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

interface ComboboxProps {
  selectableOptions: Array<{ value: string; label: string; keywords?: string[] }>
  value?: string
  onValueChange?: (value: string) => void
  placeholder?: string
  searchPlaceholder?: string
  emptyMessage?: string
  buttonWidth?: string
  wrapperClassName?: string
  triggerClassName?: string
  contentClassName?: string
  disabled?: boolean
}

export function Combobox({
  selectableOptions,
  value: controlledValue,
  onValueChange,
  placeholder = "Select option...",
  searchPlaceholder = "Search...",
  emptyMessage = "No option found.",
  buttonWidth = "w-full",
  wrapperClassName,
  triggerClassName,
  contentClassName,
  disabled = false,
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false)
  const [internalValue, setInternalValue] = React.useState("")

  // Use controlled value if provided, otherwise use internal state
  const value = controlledValue !== undefined ? controlledValue : internalValue
  const setValue =
    controlledValue !== undefined ? onValueChange : setInternalValue

  const handleSelect = (searchValue: string) => {
    // Extract the actual value from the search value (everything before the first |)
    const actualValue = searchValue.split('|')[0]
    const newValue = actualValue === value ? "" : actualValue
    setValue?.(newValue)
    setOpen(false)
  }

  // Create searchable values that include both value and label for better search
  const createSearchValue = (option: { value: string; label: string; keywords?: string[] }) => {
    const searchTerms = [
      option.value,
      option.label,
      ...(option.keywords || [])
    ].join(' ')
    return `${option.value}|${searchTerms}`
  }

  return (
    <div className={cn(wrapperClassName)}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild className={cn(triggerClassName)}>
          <Button
            variant='outline'
            role='combobox'
            aria-expanded={open}
            disabled={disabled}
            className={cn(
              buttonWidth,
              "justify-between",
              disabled && "cursor-not-allowed opacity-50"
            )}
          >
            {value
              ? selectableOptions.find(
                  (selectableOption) => selectableOption.value === value
                )?.label
              : placeholder}
            <ChevronsUpDownIcon className='ml-2 h-4 w-4 shrink-0 opacity-50' />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className={cn(
            "p-0 z-50 bg-background overflow-hidden",
            contentClassName
          )}
          style={{ width: "var(--radix-popover-trigger-width)" }}
        >
          <Command>
            <CommandInput placeholder={searchPlaceholder} />
            <CommandList>
              <CommandEmpty>{emptyMessage}</CommandEmpty>
              <CommandGroup>
                {selectableOptions.map((selectableOption) => (
                  <CommandItem
                    key={selectableOption.value}
                    value={createSearchValue(selectableOption)}
                    onSelect={handleSelect}
                    className='cursor-pointer hover:bg-primary/10'
                  >
                    <CheckIcon
                      className={cn(
                        "mr-2 h-4 w-4",
                        value === selectableOption.value
                          ? "opacity-100"
                          : "opacity-0"
                      )}
                    />
                    {selectableOption.label}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  )
}
