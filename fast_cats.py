import getpass
import keyring
import logging
import re
import requests




def main():
    logger = logging.getLogger(__name__)
    logging.basicConfig(filename='fast_cats.log', level=logging.INFO, format='%(asctime)s %(message)s')


    DEBUGGING = True
    if DEBUGGING: # remember your credentials
        input_netid = keyring.get_password("DEBUG","USER")
        if not input_netid:
            input_netid = input("netid: ")
            keyring.set_password("DEBUG","USER",input_netid)
        input_password = keyring.get_password("DEBUG","PASSWORD")
        if not input_password:
            input_password = getpass.getpass("password: ")
            keyring.set_password("DEBUG","PASSWORD",input_password)
    else: # clear cache if it exists, get credentials
        keyring.set_password("DEBUG","USER","")
        keyring.set_password("DEBUG","PASSWORD","")
        input_netid = input("netid: ")
        input_password = getpass.getpass("password: ")
    
    with requests.Session() as s:
        # go to log in page to get session
        login_url = "https://groups.richmond.edu/login"
        login_page = s.get(login_url)

        logger.info("obtained session")

        # log in
        login_payload = {"netid": input_netid, "password": input_password, "submit": "1"}

        login_response = s.post(login_url, data=login_payload, cookies=login_page.cookies)
        if login_response.status_code != 200:
            # something went wrong
            logger.error("couldn't log into cats as "+input_netid)
            exit(1)
        groups_page = login_response.text

        logger.info(f"logged in as {input_netid}, finding searching groups...")

        # set headers to something NOT suspicious (they will give you a 404 otherwise)
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Content-Length": "0",
            "Cookie": "catsgroups="+s.cookies.get_dict()['catsgroups'],
            "Host": "groups.richmond.edu",
            "Origin": "https://groups.richmond.edu",
            "Referer": "https://groups.richmond.edu/dashboard/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "Windows"
        }

        # get groups list (useful for getting GIDs)
        get_groups_url = "https://groups.richmond.edu/groups/mine/?order_by=GROUP_NAME&direction=ASC"
        my_groups = s.post(get_groups_url, headers=headers)


        group_matches = re.findall(r"<tr id=\"(\d+)\".+\n.+\"group-name\">(.+)<", my_groups.text)
        
        logger.info(f"found {len(group_matches)} groups")

        for gid, gname in group_matches:
            logger.info(f"Members in group {gname} ({gid}):")
            members_url = f"https://groups.richmond.edu/members/{gid}"
            members = s.post(members_url, headers=headers)

            for member in re.findall(r"<tr id=\".+\">\n(.+\n.+\n.+\n.+\n.+)\n.+<td class=", members.text):
                first, last, department, user_type, netid = re.findall(r"td>(.*)<",member)
                logger.info(f"\t{first}, {last}, {department}, {user_type}, {netid}")

            logger.info(f"attempting to add user to group {gname}")
            new_netid = "rcargill"
            add_member_url = f"https://groups.richmond.edu/members/add/{gid}/{new_netid}"
            add_member_result = s.post(add_member_url, headers=headers)

            print(add_member_result.status_code)
            print(add_member_result.text)
            exit()
        

if __name__ == "__main__":
    main()