from .get_folder_by_title import GetFolderByTitle
from .get_folders import GetFolders
from .update_folder import UpdateFolder


class Folders(GetFolderByTitle, GetFolders, UpdateFolder):
    pass
