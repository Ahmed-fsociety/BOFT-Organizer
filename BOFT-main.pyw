import os
import shutil

def organize_files_by_type(directory):
    # Check directory 
    if not os.path.exists(directory):
        print("The specified directory does not exist.")
        return
    
    os.chdir(directory)

    # Loop through the files in the directory
    for filename in os.listdir(directory):
        full_path = os.path.join(directory, filename)
        
        
        if os.path.isdir(full_path):
            continue
        
        # Get the file extension
        file_extension = filename.split('.')[-1]
        
        # Create a new folder based on the file extension
        folder_name = file_extension.lower() + "_files"
        
        if not os.path.exists(folder_name):
            os.mkdir(folder_name)
        
        dest_path = os.path.join(folder_name, filename)
        
        # Move the file to the appropriate folder
        shutil.move(full_path, dest_path)
        print(f"Moved {filename} to {folder_name}/")

def add_watermark():
    print("\n--- Made by Ahmed Elbaroudy ---\n")

if __name__ == "__main__":
    directory_to_organize = input("Enter the directory path to organize: ")
    organize_files_by_type(directory_to_organize)
    
    add_watermark()
    
    input("Press Enter to exit...")
