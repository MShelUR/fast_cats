import argparse
import getpass
import keyring
import logging
import os
import re
import requests
from sys import exit, path
from tqdm import tqdm



__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

path.append(f'{__location__}/.cats')
from cryptogra_fy import get_credentials


class Fast_cats_session:
    login_url = "https://groups.richmond.edu/login"
    get_groups_url = "https://groups.richmond.edu/groups/mine/?order_by=GROUP_NAME&direction=ASC"
    members_url = "https://groups.richmond.edu/members"
    add_member_url = "https://groups.richmond.edu/members/add"
    del_member_url = "https://groups.richmond.edu/members/delete"

    def __init__(self, netid, password):
        self.session = requests.Session()
        self.groups = {}
        self.members = {}
        # get session from going to page
        logger.debug("obtaining session")
        login_page = self.session.get(self.login_url)
        # log in
        login_payload = {"netid": netid, "password": password, "submit": "1"}
        login_response = self.session.post(self.login_url, data=login_payload, cookies=login_page.cookies)
        if login_response.status_code != 200:
            logger.error(f"couldn't login as user {netid}")
            raise ValueError(f"Couldn't log into CATS as user {netid}")
            exit(1)
        logger.debug(f"logged in as {netid}")
        #  make headers that look like a browser with session and cookies
        self.headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Content-Length": "0",
            "Cookie": "catsgroups="+self.session.cookies.get_dict()['catsgroups'],
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
        # get groups cache
        self.get_groups()

    def __del__(self):
        if self.session:
            self.session.close()

    def get_groups(self):
        # get (group id, group name) list
        logger.debug("found groups:")
        groups_response = self.session.post(self.get_groups_url, headers=self.headers)
        groups = re.findall(r"<tr id=\"(\d+)\".+\n.+\"group-name\">(.+)<", groups_response.text)
        for group in groups:
            gid = group[0]
            gname = group[1]
            self.groups[gid] = gname
            logger.debug(f"\t{gname}: {gid}")
        return self.groups

    def get_group_gid(self,group_name):
        logger.debug(f"trying to find gid for group {group_name}")
        for gid in self.groups:
            if self.groups[gid].lower() == group_name.lower():
                logger.debug(f"\tgroup {group_name} has gid {gid}")
                return gid
        raise Exception(f"User does not have access to a group named '{group_name}'")

    def get_users_in_group(self, gid):
        # get every user (first, last, department, type, netid) in group, build cache
        logger.debug(f"getting users in group {gid}...")
        members_result = self.session.post(self.members_url+"/"+gid, headers=self.headers)
        members = [re.findall(r"td>(.*)<",member) for member in re.findall(r"<tr id=\".+\">\n(.+\n.+\n.+\n.+\n.+)\n.+<td class=", members_result.text)]
        # build local cache to verify existence before adding/removing users later
        self.members[gid] = [member[4] for member in members] # member[4] is netid
        logger.debug(f"found {len(members)} users in group {gid}")
        return members

    def add_user_to_group(self, gid, user_netid):
        # add user to group

        logger.debug(f"adding user {user_netid} to group {gid}...")
        # check if user already in group
        if self.is_in_group(gid,user_netid):
            logger.debug(f"\t user {user_netid} was already in group, skipping")
            return 0 # user is in group

        # try to add user
        add_member_result = self.session.post(self.add_member_url+"/"+gid+"/"+user_netid, headers=self.headers)
        if add_member_result.status_code != 200:
            logger.error(f"Could not add {user_netid} to group {gid}")
            raise Exception(f"Could not add {user_netid} to group {gid}")
            exit(1)
        logger.debug(f"\tuser {user_netid} added to group {gid}")
        return 0

    def remove_user_from_group(self, gid, user_netid):
        # remove user from group

        logger.debug(f"removing user {user_netid} from group {gid}...")
        # check if user already removed from group
        if not self.is_in_group(gid,user_netid):
            logger.debug(f"\t user {user_netid} not in group, skipping")
            return 0 # user isn't in group
        
        # try removing user from group
        del_member_result = self.session.post(self.del_member_url+"/"+gid+"/"+user_netid, headers=self.headers)
        if del_member_result.status_code != 200:
            logger.error(f"Could not delete {user_netid} from group {gid}")
            raise Exception(f"Could not delete {user_netid} from group {gid}")
            exit(1)
        logger.debug(f"user {user_netid} removed from group {gid}")
        return 0

    def is_in_group(self, gid, user_netid):
        # check if user is in group

        logger.debug(f"\tchecking if user {user_netid} is in group {gid}...")
        # check if group exists in cache, else update cache
        if not self.members.get(gid):
            self.get_users_in_group(gid)
        # check if user in group
        if user_netid in self.members[gid]:
            logger.debug(f"\tUser is in group")
            return True
        logger.debug(f"\tUser is not in group")
        return False
        


def main(args):

    group = args.group
    netid_input = args.input
    do_it = args.do_it
    remove = args.remove
    
    users = []
    try: # if it's a file, read it
        with open(netid_input) as in_file:
            users = in_file.read().split()
    except: # if it isn't assume a netid
        users = [netid_input]

    
    netid, password = get_credentials()
    s = Fast_cats_session(netid,password)

    group_gid = s.get_group_gid(group)
    for netid in tqdm(users):
        if remove:
            logger.info(f"adding {netid} to group {group} (gid {group_gid})")
            if do_it: 
                s.remove_user_from_group(group_gid,netid)
        else:
            logger.info(f"adding {netid} to group {group} (gid {group_gid})")
            if do_it: 
                s.add_user_to_group(group_gid,netid)
        

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logging.basicConfig(filename=f'{__location__}/log_fast_cats.log', level=logging.DEBUG, format='%(asctime)s %(message)s')

    parser = argparse.ArgumentParser(prog="fastcats", 
        description="""
    Create, read, and remove 
    accounts on CATS.
    What CATS does, FastCATS does better!
                        -----
             (\___//)  -----    ...
            (= *.* =)    -----  .   .
                        ----      ..
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-g', '--group', type=str, default='HPC',
        help="Name of group to add the users to. Defaults to HPC (for spydur access)")
    parser.add_argument('-i', '--input', type=str, default="",
        help="Input file name with netids, or the one netid to be added.")
    parser.add_argument('-r', '--remove', action='store_true',
        help="Remove the provided netids from the group.")
    parser.add_argument('-z', '--zap', action='store_true',
        help="Zap the previous log file out of existence!")

    parser.add_argument('--do-it', action='store_true', 
        help="""
    Adding this switch will execute the commands
    as the program runs rather than print what
    actions will be taken.
        """)
    
    args = parser.parse_args()

    if args.zap:
        try:
            os.remove(f'{__location__}/log_fast_cats.log')
        except:
            pass

    if not args.group:
        print("At least one group must be named for this program to run.")
        exit(0)
    if not args.input:
        print("At least one netid or file containing netids must be named.")
        exit(0)

    
    main(args)