export function extract_youtube_video_id(url) {
    const regex = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/;
    const match = url.match(regex);
    return match ? match[1] : null;
}

// Seconds to MM:SS or HH:MM:SS
export function format_duration(seconds) {
    if (!seconds && seconds !== 0) return "00:00";
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    if (hours > 0) {
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    } else {
        return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    }
}

// YYYYMMDD to Jan 24, 2025
export function format_youtube_date(dateStr) {
    if (!dateStr) return '';
    const year = dateStr.substring(0, 4);
    const month = parseInt(dateStr.substring(4, 6)) - 1;
    const day = parseInt(dateStr.substring(6, 8));
    const date = new Date(year, month, day);
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'];
    return `${monthNames[month]} ${day}, ${year}`;
}

// Unix timestamp to just now, x minutes ago, x hours ago, x days ago, Jan 24, 2025
export function format_timestamp(timestamp) {
    if (!timestamp) return '';

    const date = new Date(timestamp * 1000); // Convert seconds to milliseconds
    const now = new Date();
    const diffMs = now - date;

    // Less than a day ago
    if (diffMs < 24 * 60 * 60 * 1000) {
        const hours = Math.floor(diffMs / (60 * 60 * 1000));
        if (hours < 1) {
            const minutes = Math.floor(diffMs / (60 * 1000));
            return minutes <= 1 ? 'just now' : `${minutes} minutes ago`;
        }
        return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`;
    }

    // Less than a week ago
    if (diffMs < 7 * 24 * 60 * 60 * 1000) {
        const days = Math.floor(diffMs / (24 * 60 * 60 * 1000));
        return `${days} ${days === 1 ? 'day' : 'days'} ago`;
    }

    // Format as date
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'];
    return `${monthNames[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

// POSIX filepath to parent dir path (with /Users/<username> --> ~)
export function format_local_path(filepath) {
    if (!filepath) return 'Local file';

    // Replace /Users/<username>/ with ~/
    const usersPattern = /^\/Users\/[^\/]+\//;
    const homePath = filepath.replace(usersPattern, '~/');

    // Get directory path without filename
    const lastSlashIndex = homePath.lastIndexOf('/');
    if (lastSlashIndex !== -1) {
        return homePath.substring(0, lastSlashIndex);
    }

    return homePath;
}

// Capitalize string
export function capitalize_string(str) {
    if (!str) return str;
    return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
  }