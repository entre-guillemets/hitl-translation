// src/components/ui/multi-select.tsx
"use client";

import React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ChevronDown, X, XCircle } from 'lucide-react';

interface Option {
  label: string;
  value: string;
}

interface MultiSelectProps {
  options: Option[];
  selectedValues: string[];
  onSelectionChange: (values: string[]) => void;
  placeholder?: string;
  className?: string;
}

export const MultiSelect: React.FC<MultiSelectProps> = ({
  options,
  selectedValues,
  onSelectionChange,
  placeholder = "Select options",
  className = "",
}) => {
  const handleSelectChange = (value: string, checked: boolean) => {
    if (checked) {
      onSelectionChange([...selectedValues, value]);
    } else {
      onSelectionChange(selectedValues.filter(item => item !== value));
    }
  };

  const removeItem = (value: string) => {
    onSelectionChange(selectedValues.filter(item => item !== value));
  };

  const clearAll = () => {
    onSelectionChange([]);
  };

  const getSelectedLabels = () => {
    return options
      .filter(option => selectedValues.includes(option.value))
      .map(option => option.label);
  };

  return (
    <div className={className}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            className="w-full justify-between min-h-10 h-auto py-2" // Added h-auto and py-2 for dynamic height
          >
            <div className="flex flex-wrap gap-1 flex-1 text-left">
              {selectedValues.length === 0 ? (
                <span className="text-muted-foreground py-1">{placeholder}</span>
              ) : (
                <div className="flex flex-wrap gap-1 max-w-full">
                  {getSelectedLabels().map((label, index) => (
                    <Badge
                      key={index}
                      variant="secondary"
                      className="text-xs flex items-center gap-1"
                    >
                      <span className="truncate max-w-[100px]">{label}</span>
                      <X
                        className="h-3 w-3 cursor-pointer hover:bg-gray-300 rounded-full"
                        onClick={(e) => {
                          e.stopPropagation();
                          const option = options.find(opt => opt.label === label);
                          if (option) removeItem(option.value);
                        }}
                      />
                    </Badge>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center gap-1 ml-2">
              {selectedValues.length > 0 && (
                <XCircle
                  className="h-4 w-4 text-gray-400 hover:text-gray-600 cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation();
                    clearAll();
                  }}
                  title="Clear all"
                />
              )}
              <ChevronDown className="h-4 w-4 opacity-50 flex-shrink-0" />
            </div>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-full min-w-[200px]">
          {selectedValues.length > 0 && (
            <>
              <div className="px-2 py-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearAll}
                  className="w-full text-xs h-6"
                >
                  <XCircle className="h-3 w-3 mr-1" />
                  Clear All ({selectedValues.length})
                </Button>
              </div>
              <div className="border-t mx-2 my-1"></div>
            </>
          )}
          {options.map((option) => (
            <DropdownMenuCheckboxItem
              key={option.value}
              checked={selectedValues.includes(option.value)}
              onCheckedChange={(checked) => 
                handleSelectChange(option.value, checked)
              }
              onSelect={(e) => e.preventDefault()}
            >
              {option.label}
            </DropdownMenuCheckboxItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};
