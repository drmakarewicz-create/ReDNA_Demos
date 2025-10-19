import * as React from "react";

export interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
}

const TabsContext = React.createContext<{
  value: string;
  onValueChange: (value: string) => void;
}>({ value: "", onValueChange: () => {} });

export function Tabs({ defaultValue = "", value: controlledValue, onValueChange, children, ...props }: TabsProps) {
  const [internalValue, setInternalValue] = React.useState(defaultValue);
  const value = controlledValue !== undefined ? controlledValue : internalValue;
  const handleValueChange = onValueChange || setInternalValue;

  return (
    <TabsContext.Provider value={{ value, onValueChange: handleValueChange }}>
      <div {...props}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabsList({ className = "", ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`inline-flex h-10 items-center justify-center rounded-md bg-gray-100 p-1 text-gray-500 ${className}`}
      {...props}
    />
  );
}

export interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

export function TabsTrigger({ className = "", value, ...props }: TabsTriggerProps) {
  const { value: selectedValue, onValueChange } = React.useContext(TabsContext);
  const isSelected = selectedValue === value;

  return (
    <button
      className={`inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-white transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${
        isSelected ? "bg-white text-gray-900 shadow-sm" : "text-gray-600 hover:text-gray-900"
      } ${className}`}
      onClick={() => onValueChange(value)}
      {...props}
    />
  );
}

export interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
}

export function TabsContent({ className = "", value, ...props }: TabsContentProps) {
  const { value: selectedValue } = React.useContext(TabsContext);

  if (selectedValue !== value) return null;

  return (
    <div
      className={`mt-2 ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${className}`}
      {...props}
    />
  );
}
