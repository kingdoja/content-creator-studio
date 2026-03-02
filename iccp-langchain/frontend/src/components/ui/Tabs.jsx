import { createContext, useContext, useState, forwardRef } from "react"
import { cn } from "../../lib/utils"

const TabsContext = createContext({ value: "", onValueChange: () => {} })

function Tabs({ defaultValue, value: controlledValue, onValueChange, children, className, ...props }) {
  const [uncontrolledValue, setUncontrolledValue] = useState(defaultValue || "")
  const value = controlledValue !== undefined ? controlledValue : uncontrolledValue
  const handleChange = (v) => {
    if (controlledValue === undefined) setUncontrolledValue(v)
    onValueChange?.(v)
  }
  return (
    <TabsContext.Provider value={{ value, onValueChange: handleChange }}>
      <div className={cn("", className)} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  )
}

const TabsList = forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground",
      className
    )}
    {...props}
  />
))
TabsList.displayName = "TabsList"

const TabsTrigger = forwardRef(({ className, value: triggerValue, ...props }, ref) => {
  const { value, onValueChange } = useContext(TabsContext)
  return (
    <button
      ref={ref}
      type="button"
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
        value === triggerValue
          ? "bg-background text-foreground shadow-sm"
          : "hover:bg-background/50",
        className
      )}
      onClick={() => onValueChange(triggerValue)}
      {...props}
    />
  )
})
TabsTrigger.displayName = "TabsTrigger"

const TabsContent = forwardRef(({ className, value: contentValue, ...props }, ref) => {
  const { value } = useContext(TabsContext)
  if (value !== contentValue) return null
  return (
    <div
      ref={ref}
      className={cn("mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2", className)}
      {...props}
    />
  )
})
TabsContent.displayName = "TabsContent"

export { Tabs, TabsList, TabsTrigger, TabsContent }
